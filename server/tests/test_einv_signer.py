"""S4.3 CAdES-BES signer contract tests (ticket #30, ITIDA spec).

The signature structure is pinned to the official SDK's parsed example
(sdk.invoicing.eta.gov.eg/signature-creation → parsed-cades-bes.txt):

* ContentInfo{signedData} wrapping a DETACHED SignedData (no eContent)
* encapContentInfo contentType = digestedData OID 1.2.840.113549.1.7.5
* digestAlgorithms / SignerInfo.digestAlgorithm = sha256, params ABSENT
* certificates = the signer's own X.509 only
* SignerInfo v1, IssuerAndSerialNumber sid, signedAttrs =
  {contentType, signingTime, messageDigest, signingCertificateV2},
  signatureAlgorithm = rsaEncryption params ABSENT,
  signature = RSA PKCS#1 v1.5 over DER(signedAttrs)

Signing input discipline: sha256 over UTF-8 bytes of the toolkit-pinned
serialized document string. The golden fixture pins the exact base64 against
the committed pinned self-signed test key (fixed signing time), so any drift
in encoding turns red byte-for-byte.
"""
import base64
import hashlib

import pytest
from datetime import datetime, timezone
from pathlib import Path

from asn1crypto import cms
from asn1crypto import x509 as asn1_x509
from cryptography import x509 as cx509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from app.einvoicing.signer import cades_bes_sign

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "einvoicing"
KEY_PEM = (FIXTURES / "pinned-test-key.pem").read_bytes()
CERT_PEM = (FIXTURES / "pinned-test-cert.pem").read_bytes()
SIGNING_TIME = datetime(2026, 8, 24, 12, 0, 0, tzinfo=timezone.utc)

SERIALIZED = '"HEADER""RECEIPTNUMBER""R-1""TOTALAMOUNT""114.00"'


def _params_absent(alg) -> bool:
    """AlgorithmIdentifier carries ONLY the OID (no NULL parameter byte)."""
    return not alg.dump().endswith(b"\x05\x00")


def _pinned():
    key = load_pem_private_key(KEY_PEM, password=None)
    cert = asn1_x509.Certificate.load(
        cx509.load_pem_x509_certificate(CERT_PEM).public_bytes(serialization.Encoding.DER)
    )
    return key, cert


def test_signature_matches_official_cades_bes_structure_and_verifies():
    """Parsed structure equals the SDK's parsed-cades-bes.txt shape; the RSA
    signature verifies over the DER-encoded signed attributes."""
    key, cert = _pinned()
    b64 = cades_bes_sign(SERIALIZED, key=key, cert=cert, signing_time=SIGNING_TIME)
    info = cms.ContentInfo.load(base64.b64decode(b64))

    assert info["content_type"].native == "signed_data"
    signed_data = info["content"]
    assert signed_data["version"].native == "v3"
    # sha256 with ABSENT parameters (official dump shows a bare OID)
    digest_alg = signed_data["digest_algorithms"][0]
    assert digest_alg["algorithm"].native == "sha256"
    assert _params_absent(digest_alg)

    # detached: encapContentInfo carries ONLY the digestedData content type
    eci = signed_data["encap_content_info"]
    assert eci["content_type"].native == "digested_data"
    assert "1.2.840.113549.1.7.5" == str(eci["content_type"])
    # no eContent: the DER of encapContentInfo is just the OID in a SEQUENCE
    assert eci.dump() == cms.EncapsulatedContentInfo({
        "content_type": "digested_data"
    }).dump()

    # exactly the signer's own certificate
    certs = list(signed_data["certificates"])
    assert len(certs) == 1
    assert certs[0].chosen.dump() == cert.dump()

    # --- SignerInfo ---
    signer = signed_data["signer_infos"][0]
    assert signer["version"].native == "v1"
    iasn = signer["sid"].chosen
    assert iasn["serial_number"].native == cert.serial_number
    assert iasn["issuer"].dump() == cert.issuer.dump()
    assert signer["digest_algorithm"]["algorithm"].native == "sha256"
    assert _params_absent(signer["digest_algorithm"])

    attrs = {str(a["type"]): a["values"] for a in signer["signed_attrs"]}
    content_type_oid = "1.2.840.113549.1.9.3"
    signing_time_oid = "1.2.840.113549.1.9.5"
    message_digest_oid = "1.2.840.113549.1.9.4"
    scv2_oid = "1.2.840.113549.1.9.16.2.47"
    assert set(attrs) == {content_type_oid, signing_time_oid, message_digest_oid, scv2_oid}
    assert str(attrs[content_type_oid][0]) == "1.2.840.113549.1.7.5"
    digest = hashlib.sha256(SERIALIZED.encode("utf-8")).digest()
    assert attrs[message_digest_oid][0].native == digest

    ess_cert = attrs[scv2_oid][0]["certs"][0]
    cert_hash = hashlib.sha256(cert.dump()).digest()
    # hashAlgorithm ABSENT: the sha256 OID must never appear inside the
    # signingCertificateV2 value — certHash is its first field (official dump)
    scv2_der = attrs[scv2_oid][0].dump()
    assert ess_cert["cert_hash"].native == cert_hash
    assert ess_cert["issuer_serial"]["serial_number"].native == cert.serial_number
    assert b"\x60\x86H\x01e\x03\x04\x02\x01" not in scv2_der

    # signatureAlgorithm = rsaEncryption with ABSENT parameters
    sig_alg = signer["signature_algorithm"]
    assert sig_alg["algorithm"].native == "rsassa_pkcs1v15"
    assert _params_absent(sig_alg)

    # the RSA signature covers the DER of the re-tagged SET OF signedAttrs
    key.public_key().verify(
        signer["signature"].native,
        signer["signed_attrs"].untag().dump(),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )


def test_signature_is_byte_stable_against_golden_fixture():
    """Same pinned key + fixed signing time ⇒ the exact committed base64."""
    key, cert = _pinned()
    golden = (FIXTURES / "cades_golden_b64.txt").read_text().strip()
    assert cades_bes_sign(SERIALIZED, key=key, cert=cert, signing_time=SIGNING_TIME) == golden


def test_signed_attrs_are_der_set_of_ordered():
    """The RSA input must be a DER SET OF (members sorted by encoded bytes)."""
    key, cert = _pinned()
    b64 = cades_bes_sign(SERIALIZED, key=key, cert=cert, signing_time=SIGNING_TIME)
    signer = cms.ContentInfo.load(base64.b64decode(b64))["content"]["signer_infos"][0]
    encoded = [m.dump() for m in signer["signed_attrs"]]
    assert encoded == sorted(encoded)
    # the RSA-covered bytes are exactly the SET OF re-encoding of those members
    body = b"".join(encoded)
    n = len(body)
    if n < 0x80:
        header = b"\x31" + bytes([n])
    else:
        length = n.to_bytes((n.bit_length() + 7) // 8, "big")
        header = b"\x31" + bytes([0x80 + len(length)]) + length
    attrs_der = signer["signed_attrs"].untag().dump()
    assert attrs_der == header + body


def test_load_signer_reads_pem_paths_and_produces_verifiable_signature(monkeypatch):
    from app.core.config import settings
    from app.einvoicing.signer import Signer, load_signer

    monkeypatch.setattr(settings, "eta_key_path", str(FIXTURES / "pinned-test-key.pem"))
    monkeypatch.setattr(settings, "eta_cert_path", str(FIXTURES / "pinned-test-cert.pem"))
    signer = load_signer()
    assert isinstance(signer, Signer)
    info = cms.ContentInfo.load(base64.b64decode(signer.sign(SERIALIZED)))
    pub = cx509.load_pem_x509_certificate(CERT_PEM).public_key()
    si = info["content"]["signer_infos"][0]
    pub.verify(si["signature"].native, si["signed_attrs"].untag().dump(),
               padding.PKCS1v15(), hashes.SHA256())


def test_load_signer_without_configured_paths_raises_unavailable(monkeypatch):
    from app.core.config import settings
    from app.einvoicing.signer import SignerUnavailable, load_signer

    monkeypatch.setattr(settings, "eta_key_path", None)
    monkeypatch.setattr(settings, "eta_cert_path", None)
    with pytest.raises(SignerUnavailable):
        load_signer()


def test_load_signer_with_malformed_key_raises_unavailable(monkeypatch, tmp_path):
    from app.core.config import settings
    from app.einvoicing.signer import SignerUnavailable, load_signer

    bad = tmp_path / "key.pem"
    bad.write_text("not a pem at all")
    monkeypatch.setattr(settings, "eta_key_path", str(bad))
    monkeypatch.setattr(settings, "eta_cert_path", str(FIXTURES / "pinned-test-cert.pem"))
    with pytest.raises(SignerUnavailable):
        load_signer()


def test_load_signer_with_missing_file_raises_unavailable(monkeypatch, tmp_path):
    from app.core.config import settings
    from app.einvoicing.signer import SignerUnavailable, load_signer

    monkeypatch.setattr(settings, "eta_key_path", str(tmp_path / "absent.pem"))
    monkeypatch.setattr(settings, "eta_cert_path", str(FIXTURES / "pinned-test-cert.pem"))
    with pytest.raises(SignerUnavailable):
        load_signer()


def test_load_signer_with_non_rsa_key_raises_unavailable(monkeypatch, tmp_path):
    from cryptography.hazmat.primitives.asymmetric import ec

    from app.core.config import settings
    from app.einvoicing.signer import SignerUnavailable, load_signer

    key = ec.generate_private_key(ec.SECP256R1())
    pem = tmp_path / "ec.pem"
    pem.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    monkeypatch.setattr(settings, "eta_key_path", str(pem))
    monkeypatch.setattr(settings, "eta_cert_path", str(FIXTURES / "pinned-test-cert.pem"))
    with pytest.raises(SignerUnavailable):
        load_signer()


def test_load_signer_with_encrypted_key_raises_unavailable(monkeypatch, tmp_path):
    """Passphrase-protected PEM (the common eSeal export shape) raises
    TypeError inside cryptography — it must still become a refusal."""
    from app.core.config import settings
    from app.einvoicing.signer import SignerUnavailable, load_signer

    key = load_pem_private_key(KEY_PEM, password=None)
    encrypted = tmp_path / "encrypted.pem"
    encrypted.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(b"secret"),
    ))
    monkeypatch.setattr(settings, "eta_key_path", str(encrypted))
    monkeypatch.setattr(settings, "eta_cert_path", str(FIXTURES / "pinned-test-cert.pem"))
    with pytest.raises(SignerUnavailable):
        load_signer()


def test_load_signer_with_mismatched_cert_raises_unavailable(monkeypatch, tmp_path):
    """A key that doesn't pair with the certificate must refuse up front —
    not surface later as per-document rejections at ETA verification."""
    from datetime import datetime, timedelta as td, timezone as tz

    from app.core.config import settings
    from app.einvoicing.signer import SignerUnavailable, load_signer

    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = cx509.Name([
        cx509.NameAttribute(cx509.oid.NameOID.COUNTRY_NAME, "EG"),
        cx509.NameAttribute(cx509.oid.NameOID.COMMON_NAME, "Wrong Cert"),
    ])
    now = datetime.now(tz.utc)
    cert = (
        cx509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(other_key.public_key())
        .serial_number(cx509.random_serial_number())
        .not_valid_before(now).not_valid_after(now + td(days=365))
        .sign(other_key, hashes.SHA256())
    )
    wrong_cert = tmp_path / "wrong.crt"
    wrong_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    # the pinned key + someone else's cert
    monkeypatch.setattr(settings, "eta_key_path", str(FIXTURES / "pinned-test-key.pem"))
    monkeypatch.setattr(settings, "eta_cert_path", str(wrong_cert))
    with pytest.raises(SignerUnavailable, match="does not match"):
        load_signer()
