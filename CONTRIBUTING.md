# Contributing

Thank you for trying Rant Agent. Small fixes, clear bug reports, setup improvements and model-compatibility results are welcome.

1. Fork the repository and make a branch for one concrete change.
2. Run `./start.sh` to install the base environment. Model downloads are optional.
3. Keep changes in the local package. Do not add external cloud credentials, account databases or private project history.
4. Run backend tests, TypeScript checks and a frontend build. For UI changes, check both themes. For provider changes, add a local mocked-contract test; paid generation must be opt-in.
5. Explain the user-visible behavior, how you tested it, and known limits in your pull request.

```bash
.venv/bin/python -m unittest discover -s sever-ide/backend -p 'test_*.py'
cd sever-ide
npm run typecheck
npm run build
```

`sever-ide/app` and `components` contain the interface; `backend` serves it and runs jobs. `local-assistant` holds shared bounded tools. `scripts/launch.py` owns installation/build/startup. The historical `sever-ide` folder name is retained for compatibility.

Generated logos/icons are committed so users do not need design tools. To rebuild the favicon from the supplied R glyph after an intentional asset change, run `.venv/bin/python scripts/build_icons.py`; it uses the frontend's Sharp dependency and base Pillow installation. Original brand SVG paths should remain intact.

Do not include secrets, personal data, third-party weights or assets you do not have permission to share. Contributions are licensed under the repository's MIT license. Be respectful and focus discussions on concrete behavior and evidence.

## Translations

UI strings use `t()` from `sever-ide/lib/i18n.ts`. Keep English translations in `sever-ide/lib/translations.json` and subscribe render functions with `useLanguage()`. Never translate user-authored conversations, names, file contents or provider identifiers. Run `npm run test:i18n` from sever-ide; also verify EN/RU switching and refresh persistence in a browser.
