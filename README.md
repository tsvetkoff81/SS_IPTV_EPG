# SS IPTV — компактная программа передач (XMLTV)

Публичный репозиторий содержит **только публичные идентификаторы ТВ-каналов и код обработки XMLTV**. Здесь **нет** персонального IPTV M3U, потоковых адресов, логинов, паролей или токенов.

## Назначение

Сокращать EPG провайдера `https://bobor.pm/epg/epg-lite.xml` (около 44 МБ) до размера не более 4,5 МБ для SS IPTV. Включаются 766 XMLTV идентификаторов, относящихся к 14 предварительно выбранным группам телеканалов (в исходном M3U было 1 489 записей в этих группах, из них 820 сопоставились с EPG). Другие группы и личный плейлист в публикацию не попадают.

## Автоматизация

Workflow: [Publish SS IPTV EPG](../../actions/workflows/publish-epg.yml).

- Запуск вручную (Actions → Publish SS IPTV EPG → Run workflow) или по расписанию.
- 05:15 и 17:15 по UTC+03 (Москва / Турция).
- Выгружается EPG текущего календарного дня и ближайших часов.
- Размер XML — до 4 500 000 байт (динамически сокращается горизонт).
- Создаётся временный сайт только из `epg.xml` и минимальной `index.html`.
- **Нет ежедневных коммитов 4-мегабайтных файлов**: публикация через GitHub Pages artifact.

## Первый запуск (нужно сделать вручную)

1. Открыть **Settings → Pages**: https://github.com/tsvetkoff81/SS_IPTV_EPG/settings/pages
2. В **Build and deployment → Source** выбрать **GitHub Actions** (не «Deploy from a branch»).
3. Открыть https://github.com/tsvetkoff81/SS_IPTV_EPG/actions/workflows/publish-epg.yml.
4. Нажать **Run workflow**, выбрать ветку `main`. Дождаться двух зелёных заданий: `build` и `deploy`.
5. Проверить URL: `https://tsvetkoff81.github.io/SS_IPTV_EPG/epg.xml`. При ошибке открыть лог workflow.

**Не вставлять URL в персональный M3U до проверки публикации и HTTP-заголовков.**

## Ограничение SS IPTV

Для универсальной совместимости SS IPTV требует HTTP CORS-заголовки `Access-Control-Allow-Origin: *`, `Access-Control-Allow-Methods`, `Access-Control-Allow-Headers`, `Access-Control-Expose-Headers`. У GitHub Pages нет произвольной конфигурации этих заголовков. Если после развёртывания они отсутствуют либо SS IPTV не загружает программу, потребуется бесплатный Cloudflare Pages с файлом `_headers` и тем же EPG из этого репозитория. Доступ по браузеру сам по себе ещё не означает поддержку приложением.

Официальные требования SS IPTV: https://www.ss-iptv.com/en/users/12-content-en/operators

**Логотипы намеренно не меняются** — это отдельный этап.
