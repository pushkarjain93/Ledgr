/**
 * A short two-note chime for when new data arrives.
 *
 * Synthesised with the Web Audio API rather than shipped as an audio file:
 * no binary asset, no network fetch, and nothing to mis-load. Two soft sine
 * tones with a quick fade — audible enough to notice, quiet enough not to
 * startle someone reviewing payments.
 *
 * Browsers block audio until the page has had a user gesture. By the time a
 * batch notification fires the user has already logged in and clicked, so it
 * normally plays — but every failure path is swallowed. A silent chime is a
 * non-event; an exception thrown from a notification is a bug.
 */
let audioContext: AudioContext | null = null

function getContext(): AudioContext | null {
  try {
    if (!audioContext) {
      const Ctor =
        window.AudioContext ??
        (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
      if (!Ctor) return null
      audioContext = new Ctor()
    }
    // Autoplay policies suspend a context created before any gesture.
    if (audioContext.state === 'suspended') void audioContext.resume()
    return audioContext
  } catch {
    return null
  }
}

function tone(ctx: AudioContext, frequency: number, startAt: number, duration: number) {
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.type = 'sine'
  osc.frequency.value = frequency

  // Fade in and out — an abrupt start/stop on a sine wave clicks audibly.
  gain.gain.setValueAtTime(0, startAt)
  gain.gain.linearRampToValueAtTime(0.12, startAt + 0.02)
  gain.gain.exponentialRampToValueAtTime(0.0001, startAt + duration)

  osc.connect(gain)
  gain.connect(ctx.destination)
  osc.start(startAt)
  osc.stop(startAt + duration)
}

export function playNotificationChime(): void {
  const ctx = getContext()
  if (!ctx) return
  try {
    const now = ctx.currentTime
    tone(ctx, 880, now, 0.18)         // A5
    tone(ctx, 1174.66, now + 0.12, 0.26) // D6 — rising, reads as "arrived"
  } catch {
    /* never let a notification sound break the notification */
  }
}
