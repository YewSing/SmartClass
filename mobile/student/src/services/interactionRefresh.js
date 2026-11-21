// Batch invalidations that arrive during a read into one trailing request.
// A lifecycle event also invalidates the current result, so a late open response
// cannot restore actions after a close event.
export function createInteractionRefresh(read, onResult, onError) {
  let pending = null
  let dirty = false
  let lifecycle = 0
  let stopped = false

  async function drain() {
    try {
      while (dirty && !stopped) {
        dirty = false
        const version = lifecycle
        try {
          const result = await read()
          if (!stopped && version === lifecycle) onResult(result)
        } catch (error) {
          if (!stopped && version === lifecycle) onError(error)
        }
      }
    } finally {
      pending = null
    }
  }

  return {
    refresh({ lifecycleChange = false } = {}) {
      if (stopped) return
      if (lifecycleChange) lifecycle++
      dirty = true
      pending ??= drain()
      return pending
    },
    stop() { stopped = true },
  }
}
