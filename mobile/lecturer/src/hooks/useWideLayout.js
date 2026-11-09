import { Platform, useWindowDimensions } from 'react-native'

// Desktop browser layout: side navigation + centred content column.
// Phones (and narrow browser windows) keep the bottom tabs unchanged.
export const WIDE_MIN_WIDTH = 900
export const SIDE_NAV_WIDTH = 232
export const CONTENT_MAX_WIDTH = 960

export function useWideLayout() {
  const { width } = useWindowDimensions()
  return Platform.OS === 'web' && width >= WIDE_MIN_WIDTH
}
