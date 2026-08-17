import { Badge, type BadgeTone } from './Badge';

export type StatusKind = 'saved' | 'unsaved' | 'copy' | 'offline' | 'online';

export interface StatusChipProps {
  kind: StatusKind;
  labelAr: string;
  labelEn: string;
}

const TONE: Record<StatusKind, BadgeTone> = {
  saved: 'low',
  unsaved: 'medium',
  copy: 'accent',
  offline: 'neutral',
  online: 'low',
};

/** Invoice / connectivity state chip (plan/03 §5.1, legacy status colors). */
export function StatusChip({ kind, labelAr, labelEn }: StatusChipProps) {
  return (
    <Badge tone={TONE[kind]} title={labelEn}>
      {labelAr}
    </Badge>
  );
}
