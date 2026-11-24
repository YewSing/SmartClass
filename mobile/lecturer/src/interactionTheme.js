// Colours of the live interaction screens (S38f), the same in both apps: the app theme plus one colour
// per kind of interaction. Questions teal, quick question purple, poll blue, "I don't understand" orange.
// Green is only "live / answered", red only "stop / spike".
import { C as theme } from './theme'

export const C = {
  ...theme,
  purple: '#7C3AED', purpleLt: '#F3E8FF', purpleBd: '#DDD6FE', purpleDk: '#6D28D9',
  teal: '#0D9488', tealLt: '#F0FDFA', tealBd: '#99F6E4', tealDk: '#0F766E',
  blueBd: '#BFDBFE', greenBd: '#BBF7D0', orangeBd: '#FED7AA', redBd: '#FECACA',
}

export const TONES = {
  blue: { solid: C.primary, lt: C.blueLt, bd: C.blueBd, dk: C.blueDk },
  purple: { solid: C.purple, lt: C.purpleLt, bd: C.purpleBd, dk: C.purpleDk },
  teal: { solid: C.teal, lt: C.tealLt, bd: C.tealBd, dk: C.tealDk },
  orange: { solid: C.orange, lt: C.orangeLt, bd: C.orangeBd, dk: C.orangeDk },
  green: { solid: C.green, lt: C.greenLt, bd: C.greenBd, dk: C.greenDk },
  red: { solid: C.red, lt: C.redLt, bd: C.redBd, dk: C.redDk },
  gray: { solid: C.gray500, lt: C.gray100, bd: C.border, dk: C.gray600 },
}

const REACTION_TONE = { thumbs_up: 'blue', clear: 'green', too_fast: 'orange', too_slow: 'purple' }
export const reactionTone = (kind) => REACTION_TONE[kind] ?? 'gray'
