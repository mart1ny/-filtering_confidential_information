# Contributing

## Local setup

```bash
cp .env.example .env
uv sync --all-groups
```

## Development commands

```bash
make run
make lint
make test
make format
```

## Commit style

Рекомендуемый формат:
- `Этап N: ...`
- `feat: ...`
- `fix: ...`

## Pull request checklist

- [ ] Код проходит `make lint`
- [ ] Тесты проходят `make test`
- [ ] Обновлен README/документация при изменении поведения
- [ ] Не добавлены секреты и тяжелые артефакты в git
