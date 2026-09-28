# Ротация секретов и очистка истории (не выполнена)

## Подтверждённые находки

Проверены 46 коммитов, достижимых из `main@ecd7afa17ec1166b1427ca53b041a8e4e360137f`, и все 295 уникальных текстовых blob-версий этих деревьев. Доступны ветки main и docs/architecture-audit-2026-09-28; документационная ветка наследует эту историю. Scanner искал PEM private keys/certificates, известные раскрытые credentials и literal credential assignments. Удалённые refs, forks, cached PR views, Git LFS, внешние clones и tags не подтверждены: connector отказал в чтении tags endpoint. Это явно ограничивает полноту поиска.

- `nginx/ssl/key.pem` и `nginx/ssl/cert.pem` впервые добавлены в `b449c7131471f194a09c31240cdc763ea4420e31`. Ключ находится в истории. Удаление этих двух файлов в новом коммите **не отзывает ключ и не очищает прошлые коммиты**. Сертификат сам по себе публичный, но прежнюю пару нельзя использовать.
- Общий JWT secret и Evolution authentication API key были в `SHARED/config.py`, `CARTRIDGE/app/config.py`, обоих Compose и документации; предыдущая раскладка дерева также содержит `app/config.py`, `README.md`.
- Пароли PostgreSQL были в Compose (app и standalone Evolution). Default administrator credentials — в обоих database init, README, portal/index HTML, reset scripts и тестах. Исторические пути включают `app/database.py`, `app/static/index.html`, `test_verification.py`.
- Сетевая password/community выдавались read API, а LDAP password/Evolution key — settings API для superadmin и update response. Их нельзя считать сохранёнными в тайне только потому, что значений не было в Git.

Значения намеренно не воспроизведены в этом документе. Связанные логи, артефакты и backups тоже могут содержать их.

## Немедленно rotate / revoke

1. TLS private key: создать новый ключ вне Git, выпустить новый сертификат с правильным SAN, установить пару, отозвать старый сертификат у CA, если применимо. Для self-signed убрать старый trust и распространить новый проверенным каналом.
2. JWT signing secret: новый случайный независимый ключ; завершить все существующие сессии. Проверить активные учётки и историю привилегированных действий.
3. Пароли всех default/скопированных администраторов; неизвестные и неиспользуемые accounts отключить. Не ограничиваться заменой startup seed.
4. PostgreSQL app role и Evolution role passwords во всех установках, где использовались встроенные значения; изменить роли/клиенты согласованно. Смена POSTGRES_PASSWORD в Compose сама по себе не обновляет существующий volume.
5. Evolution global authentication key и instance tokens, включая прежние предсказуемые instance tokens. Обновить клиентов; при необходимости пересоздать/перепривязать WhatsApp sessions согласованно, поскольку это прерывает отправку.
6. SSH/device passwords, SNMP communities и сетевые API credentials, которые были доступны через API. Обновить устройства и хранилище приложения согласованно. Проверить SSH host fingerprints независимо от ротации паролей.
7. LDAP bind account password и любой пароль/API key, попавший в settings responses или логи. Проверить минимальные AD privileges. Redis ранее не требовал пароль — задать новый уникальный и перезапустить клиентов.

## План history cleanup — требует отдельного подтверждения

**Ниже инструкция, не выполненные команды. Rewrite меняет SHA и требует force push. Не выполнять на рабочем checkout или без согласованного окна.**

1. Сначала закончить ротацию. Зафиксировать владельца операции и окно запрета push. Согласовать branch protection, PR, forks, CI caches, releases, artifacts и backups. Сохранить ограниченно доступную аварийную копию: она тоже содержит раскрытые secrets.
2. В отдельном закрытом каталоге получить fresh mirror `git clone --mirror https://github.com/ZQRey/REP_ZAP_INV.git`. Инвентаризировать все branches/tags/refs и запустить полный history secret scanner; локальная проверка в этом hardening охватила main, но не все возможные удалённые refs.
3. Подготовить **вне репозитория** защищённый файл replacement rules для `git-filter-repo --replace-text` со всеми подтверждёнными историческими secret values, включая старые названия/пути. Не копировать его в issue, PR, shell arguments/history, CI output. Ограничить ACL, удалить после подтверждённой операции согласно политике хранения.
4. В mirror выполнить после отдельного одобрения команды такого вида (пути placeholders заменить, не копировать буквально):

   ```text
   git filter-repo --sensitive-data-removal --invert-paths --path nginx/ssl/key.pem --path nginx/ssl/cert.pem --replace-text <SECURE_REPLACEMENTS_FILE>
   ```

   Подтвердить поддержку `--sensitive-data-removal` установленной версией git-filter-repo. Добавить все прочие обнаруженные sensitive paths. Изменение только этих PEM paths недостаточно для embedded secrets в config/Compose/старых app paths.
5. Повторно просканировать **все** refs и `git log --all`, проверить, что рабочий код и документация сохранены; составить mapping старых и новых SHA. Лишь после проверки и отдельного разрешения владельца выполнить согласованный force push обновлённых refs. Не запускать слепой `git push --mirror` — он способен удалить чужие refs.
6. Связаться с GitHub Support по удалению cached views/PR references к sensitive data согласно доступным возможностям аккаунта. Учитывать forks и чужие clones: rewrite не отзывает уже скопированные secrets. Разработчикам выдать инструкции fresh clone, запрет merge старых веток обратно и проверку незапушенной работы.
7. Пересоздать build caches/artifacts, проверить registries и внешние логи, удалить старые secrets по политике хранения. Включить push protection/secret scanning, если доступно в настройках репозитория; этот PR сам настройки аккаунта не меняет.

## Предотвращение повторения

`.gitignore` и `.dockerignore` исключают env, secret directories, ключи, credentials volumes и БД; `.env.example` пустой. CI проверяет текущий tree на private key material, tracked credential files и известные небезопасные конструкции. Ignore rules не защищают от `git add -f`, поэтому проверка должна оставаться обязательной. Полноценный scanner истории и push protection дополняют, а не заменяют ротацию.
