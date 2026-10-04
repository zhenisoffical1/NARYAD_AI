export type ReasonKey =
  | 'no_materials'
  | 'no_permit'
  | 'busy_emergency'
  | 'waiting_parts'
  | 'waiting_stop'
  | 'not_my_specialty'
  | 'duplicate'
  | 'mistake'
  | 'not_needed'

/** Уважительные причины отказа — те же, что считает рейтинг на сервере (services/quality.py). */
export const REJECT_REASONS: ReasonKey[] = ['no_materials', 'no_permit', 'busy_emergency', 'not_my_specialty']
export const PAUSE_REASONS: ReasonKey[] = ['waiting_parts', 'waiting_stop', 'no_materials', 'busy_emergency']
export const CANCEL_REASONS: ReasonKey[] = ['duplicate', 'mistake', 'not_needed']
