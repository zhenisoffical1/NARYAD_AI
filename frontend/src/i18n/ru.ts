export const ru = {
  app: {
    name: 'НарядAI',
    slogan: 'Наряд выдан — ИИ на контроле',
  },
  roles: {
    master: 'Мастер смены',
    worker: 'Исполнитель',
    boss: 'Руководитель',
    admin: 'Администратор',
  },
  login: {
    title: 'Вход',
    login: 'Логин',
    pin: 'ПИН',
    pinHint: '4 цифры',
    submit: 'Войти',
    checking: 'Проверяем…',
  },
  common: {
    logout: 'Выйти',
    switchLanguage: 'Қазақша',
    toHome: 'На главную',
    retry: 'Повторить',
  },
  screens: {
    worker: 'Мои наряды',
    master: 'Выдать наряд',
    panel: 'Панель смены',
    boss: 'Дашборд руководителя',
    admin: 'Справочники',
    devUi: 'Компоненты интерфейса',
    demo: 'Пульт демо',
    comingNext: 'Экран собирается на следующем этапе.',
  },
  live: {
    online: 'На связи',
    connecting: 'Подключаемся…',
    offline: 'Нет связи — обновим, когда сеть вернётся',
  },
  errors: {
    network: 'Нет связи с сервером. Проверьте сеть и повторите.',
    server: 'Сервер ответил ошибкой ({{status}}). Повторите через минуту.',
    notFoundTitle: 'Такой страницы нет',
    notFoundText: 'Ссылка устарела или набрана с ошибкой.',
    forbiddenTitle: 'Раздел недоступен',
    forbiddenText: 'Этот раздел для другой роли. Ваши экраны — по кнопке ниже.',
  },
}

export type Translation = typeof ru
