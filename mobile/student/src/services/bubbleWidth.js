// Android works out a shrink-to-fit Text's height from one measurement and draws it using the
// measured width. With some phone fonts that width is a hair too small: the last word wraps onto
// a line the height doesn't include, and disappears. A fixed width avoids this, because height and
// wrapping then come from the same width, so a wrapped word still shows.
const SLACK = 8             // spare room, so a message that fits on one line stays on one line
const LIST_PADDING = 24     // AssistantChat styles.list: padding 12 on each side
const BUBBLE_SHARE = 0.88   // styles.bubble: maxWidth 88%
const BUBBLE_PADDING = 24   // styles.bubble: padding 12 on each side

export function bubbleTextWidth(measuredWidth, windowWidth) {
  const widest = Math.floor((windowWidth - LIST_PADDING) * BUBBLE_SHARE - BUBBLE_PADDING)
  return Math.min(Math.ceil(measuredWidth) + SLACK, widest)
}
