import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

import { kk } from './kk'
import { ru, type Translation } from './ru'

export type Language = 'ru' | 'kk'

const STORAGE_KEY = 'naryad.lang'

function storedLanguage(): Language {
  try {
    return localStorage.getItem(STORAGE_KEY) === 'kk' ? 'kk' : 'ru'
  } catch {
    return 'ru'
  }
}

export function setLanguage(lang: Language): void {
  void i18n.changeLanguage(lang)
  document.documentElement.lang = lang
  try {
    localStorage.setItem(STORAGE_KEY, lang)
  } catch {
    // Язык просто не запомнится — интерфейс продолжит работать
  }
}

declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'translation'
    resources: { translation: Translation }
  }
}

void i18n.use(initReactI18next).init({
  resources: { ru: { translation: ru }, kk: { translation: kk } },
  lng: storedLanguage(),
  fallbackLng: 'ru',
  interpolation: { escapeValue: false },
})

document.documentElement.lang = i18n.language

export default i18n
