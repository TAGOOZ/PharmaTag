"""CAdES-BES signer per the ITIDA/ETA spec (S4.3, #30).

Signing procedure (sdk.invoicing.eta.gov.eg/signature-creation):
canonicalize (toolkit.serialize) → SHA-256 over UTF-8 bytes → CAdES-BES
signature of that hash → Base64. The CMS structure replicates the SDK's own
parsed example byte-shape:

* DETACHED SignedData v3 whose encapContentInfo names only the digestedData
  content type (OID 1.2.840.113549.1.7.5) — the document itself travels
  alongside the signature, never inside it
* sha256 digest algorithm with ABSENT parameters, rsaEncryption with ABSENT
  parameters (the official parsed dump shows bare OIDs)
* one certificate: the signer's own X.509
* SignerInfo v1 (IssuerAndSerialNumber sid) with signedAttrs =
  {contentType, signingTime, messageDigest, signingCertificateV2}; the RSA
  PKCS#1 v1.5 signature covers the DER of those attributes

Key material lives ONLY here (plan/06 R5/D17): PEM key + cert files on the
shop server (e.g. ``/etc/pharmatag/eta/``), paths from settings
(PHARMATAG_ETA_KEY_PATH / PHARMATAG_ETA_CERT_PATH). A missing or malformed
key raises :class:`SignerUnavailable`, which callers translate into a
deferred pass + audit row — never a crashed worker loop.
"""
from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from asn1crypto import cms, pem, tsp
from asn1crypto import x509 as asn1_x509
from asn1crypto.core import OctetString, UTCTime
from cryptography import x509 as cx509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key

# PKCS#7/PKCS#9 OIDs pinned by the official parsed structure
_OID_DIGESTED_DATA = "1.2.840.113549.1.7.5"
# (attribute OIDs are referenced by their asn1crypto map names below)


class SignerUnavailable(RuntimeError):
    """The eSeal key/cert is missing, unreadable or malformed."""


def cades_bes_sign(
    serialized: str,
    *,
    key: rsa.RSAPrivateKey,
    cert: asn1_x509.Certificate,
    signing_time: datetime | None = None,
) -> str:
    """Base64 CAdES-BES over the SHA-256 of a toolkit-serialized string."""
    digest = hashlib.sha256(serialized.encode("utf-8")).digest()
    when = (signing_time or datetime.now(timezone.utc)).astimezone(timezone.utc)

    # DER SET OF sorts members by their encoded bytes; the four attribute OIDs
    # (…1.9.3 / …1.9.4 / …1.9.5 / …1.9.16.2.47) fix this order deterministically.
    attrs = cms.CMSAttributes([
        _attr("content_type", [cms.ContentType("digested_data")]),
        _attr("message_digest", [OctetString(digest)]),
        _attr("signing_time", [UTCTime(when)]),
        _attr(
            "signing_certificate_v2",
            [
                _ess_cert_id_v2(cert)
            ],
        ),
    ])

    signer_info = cms.SignerInfo({
        "version": 1,
        "sid": cms.IssuerAndSerialNumber({
            "issuer": cert.issuer,
            "serial_number": cert.serial_number,
        }),
        "digest_algorithm": _sha256(),
        "signed_attrs": attrs,
        "signature_algorithm": _rsa_encryption(),
        "signature": key.sign(attrs.untag().dump(), padding.PKCS1v15(), hashes.SHA256()),
    })

    signed_data = cms.SignedData({
        "version": 3,
        "digest_algorithms": [_sha256()],
        "encap_content_info": {"content_type": _OID_DIGESTED_DATA},
        "certificates": [cert],
        "signer_infos": [signer_info],
    })
    info = cms.ContentInfo({"content_type": "signed_data", "content": signed_data})
    return base64.b64encode(info.dump()).decode("ascii")


def _sha256() -> cms.DigestAlgorithm:
    """sha256 AlgorithmIdentifier with ABSENT parameters (ITIDA shape)."""
    algorithm = cms.DigestAlgorithm({"algorithm": "sha256"})
    del algorithm["parameters"]
    return algorithm


def _rsa_encryption() -> cms.SignedDigestAlgorithm:
    """rsaEncryption AlgorithmIdentifier with ABSENT parameters (the
    official parsed dump shows a bare OID, not the conventional NULL)."""
    algorithm = cms.SignedDigestAlgorithm({"algorithm": "rsassa_pkcs1v15"})
    del algorithm["parameters"]
    return algorithm


def _attr(type_name: str, values: list) -> cms.CMSAttribute:
    return cms.CMSAttribute({"type": type_name, "values": values})


def _ess_cert_id_v2(cert: asn1_x509.Certificate) -> tsp.SigningCertificateV2:
    """SigningCertificateV2 with hashAlgorithm ABSENT (sha256 default), per
    the official parsed dump's two-field ESSCertIDv2."""
    ess = tsp.ESSCertIDv2({
        "cert_hash": OctetString(hashlib.sha256(cert.dump()).digest()),
        "issuer_serial": tsp.IssuerSerial({
            "issuer": asn1_x509.GeneralNames([
                asn1_x509.GeneralName(name="directory_name", value=cert.issuer)
            ]),
            "serial_number": cert.serial_number,
        }),
    })
    del ess["hash_algorithm"]
    return tsp.SigningCertificateV2({"certs": tsp.ESSCertIDv2s([ess])})


class Signer:
    """A loaded eSeal key+cert pair; the only module that touches the files."""

    def __init__(self, key: rsa.RSAPrivateKey, cert: asn1_x509.Certificate) -> None:
        self._key = key
        self._cert = cert

    def sign(self, serialized: str) -> str:
        """Base64 CAdES-BES signature of a toolkit-serialized document."""
        return cades_bes_sign(serialized, key=self._key, cert=self._cert)


def load_signer() -> Signer:
    """Load the configured PEM key/cert pair, or raise SignerUnavailable.

    Every misconfiguration — missing files, malformed PEM, a passphrase-
    protected key (the common shape of exported eSeal token material, which
    raises TypeError not ValueError), a non-RSA key, or a key that does not
    match the certificate — becomes one observable refusal instead of a late
    per-document failure at ETA verification time.
    """
    from app.core.config import settings

    if not settings.eta_key_path or not settings.eta_cert_path:
        raise SignerUnavailable(
            "eSeal key/cert not configured "
            "(PHARMATAG_ETA_KEY_PATH / PHARMATAG_ETA_CERT_PATH)"
        )
    try:
        key_pem = Path(settings.eta_key_path).read_bytes()
        cert_pem = Path(settings.eta_cert_path).read_bytes()
        # TypeError: encrypted PEM loaded without its passphrase
        key = load_pem_private_key(key_pem, password=None)
    except (OSError, ValueError, TypeError) as exc:
        raise SignerUnavailable(f"eSeal key/cert unusable: {exc}") from exc
    if not isinstance(key, rsa.RSAPrivateKey):
        raise SignerUnavailable("eSeal key must be an RSA private key")
    try:
        cert_x509 = cx509.load_pem_x509_certificate(cert_pem)
    except (ValueError, TypeError) as exc:
        raise SignerUnavailable(f"eSeal cert unusable: {exc}") from exc
    if key.public_key().public_numbers() != cert_x509.public_key().public_numbers():
        raise SignerUnavailable(
            "eSeal private key does not match the certificate's public key"
        )
    return Signer(key, asn1_x509.Certificate.load(pem.unarmor(cert_pem)[2]))
