export const APP_MAIN_SELECTOR = '[data-app-main]'

export function scrollAppMainToTop() {
  const main = document.querySelector(APP_MAIN_SELECTOR)
  if (main instanceof HTMLElement) {
    main.scrollTop = 0
  }
}
