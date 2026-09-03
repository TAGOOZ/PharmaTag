'use client';

import { useEffect, useState } from 'react';
import { ApiError, listParties, type Party } from '@/lib/api';
import { mapMoneyError, moneyErrorMessage } from './moneyErrors';
import PayablesPanel from './statements/PayablesPanel';
import ReceivablesPanel from './statements/ReceivablesPanel';
import StatementSection from './statements/StatementSection';
import VouchersPanel from './statements/VouchersPanel';

export default function StatementsTab({
  token,
  onAuthFail,
}: {
  token: string;
  onAuthFail: () => void;
}) {
  // One unfiltered party list shared by the statement picker and the voucher
  // form (the server returns every active party when no kind is given).
  const [parties, setParties] = useState<Party[] | null>(null);
  const [partiesError, setPartiesError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let cancelled = false;
    (async () => {
      try {
        const list = await listParties(token, undefined, controller.signal);
        if (cancelled) return;
        setParties([...list.parties].sort((a, b) => a.namee.localeCompare(b.namee)));
      } catch (err) {
        if (cancelled || (err as Error)?.name === 'AbortError') return;
        if (err instanceof ApiError && err.status === 401) {
          onAuthFail();
          return;
        }
        setParties([]);
        setPartiesError(
          err instanceof ApiError ? moneyErrorMessage(err.status, err.detail) : mapMoneyError(err),
        );
      }
    })();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [token, onAuthFail]);

  return (
    <div className="flex flex-col gap-6">
      <h2 className="pt-title text-lg">كشوفات وتسويات</h2>
      {partiesError && (
        <p className="pt-caption text-red-600" role="alert">
          {partiesError}
        </p>
      )}
      <StatementSection token={token} onAuthFail={onAuthFail} parties={parties} />
      <div className="border-t border-border pt-4">
        <PayablesPanel token={token} onAuthFail={onAuthFail} />
      </div>
      <div className="border-t border-border pt-4">
        <ReceivablesPanel token={token} onAuthFail={onAuthFail} />
      </div>
      <div className="border-t border-border pt-4">
        <VouchersPanel token={token} onAuthFail={onAuthFail} parties={parties ?? []} />
      </div>
    </div>
  );
}
