import { createRef } from 'react'

export const navigationRef = createRef()

export function navigateTo(name, params) {
  if (navigationRef.current) {
    navigationRef.current.navigate(name, params)
  }
}
