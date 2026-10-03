import type { Translation } from './ru'

export const kk: Translation = {
  app: {
    name: 'НарядAI',
    slogan: 'Наряд берілді — ЖИ бақылауда',
  },
  roles: {
    master: 'Ауысым шебері',
    worker: 'Орындаушы',
    boss: 'Басшы',
    admin: 'Әкімші',
  },
  login: {
    title: 'Кіру',
    login: 'Логин',
    pin: 'PIN',
    pinHint: '4 сан',
    submit: 'Кіру',
    checking: 'Тексеріп жатырмыз…',
  },
  common: {
    logout: 'Шығу',
    switchLanguage: 'Русский',
    toHome: 'Басты бетке',
    retry: 'Қайталау',
  },
  screens: {
    worker: 'Менің нарядтарым',
    master: 'Наряд беру',
    panel: 'Ауысым тақтасы',
    boss: 'Басшы тақтасы',
    admin: 'Анықтамалықтар',
    devUi: 'Интерфейс компоненттері',
    demo: 'Демо пульті',
    comingNext: 'Бұл экран келесі кезеңде жиналады.',
  },
  live: {
    online: 'Байланыс бар',
    connecting: 'Қосылып жатыр…',
    offline: 'Байланыс жоқ — желі қалпына келгенде жаңартамыз',
  },
  errors: {
    network: 'Сервермен байланыс жоқ. Желіні тексеріп, қайталаңыз.',
    server: 'Сервер қатемен жауап берді ({{status}}). Бір минуттан кейін қайталаңыз.',
    notFoundTitle: 'Мұндай бет жоқ',
    notFoundText: 'Сілтеме ескірген немесе қате терілген.',
    forbiddenTitle: 'Бөлім қолжетімсіз',
    forbiddenText: 'Бұл бөлім басқа рөлге арналған. Сіздің экрандарыңыз — төмендегі батырма арқылы.',
  },
}
