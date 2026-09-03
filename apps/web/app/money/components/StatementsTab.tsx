'use client';

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
  return (
    <div className="flex flex-col gap-6">
      <h2 className="pt-title text-lg">كشوفات وتسويات</h2>
      <StatementSection token={token} onAuthFail={onAuthFail} />
      <div className="border-t border-border pt-4">
        <PayablesPanel token={token} onAuthFail={onAuthFail} />
      </div>
      <div className="border-t border-border pt-4">
        <ReceivablesPanel token={token} onAuthFail={onAuthFail} />
      </div>
      <div className="border-t border-border pt-4">
        <VouchersPanel token={token} onAuthFail={onAuthFail} />
      </div>
    </div>
  );
}
