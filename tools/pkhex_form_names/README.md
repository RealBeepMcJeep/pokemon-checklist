# PKHeX form-name dump

Regenerates `references/qr-codes/gen7-form-names.json` from PKHeX's own `FormConverter` (Gen 7 context, English strings) at the commit pinned in that file.

```sh
git clone https://github.com/kwsch/PKHeX.git /tmp/pkhex && git -C /tmp/pkhex checkout 542111fc8584ff29c9d1455553b8acd0e1f8a59a
dotnet run -c Release --project tools/pkhex_form_names -p:PKHeXCore=/tmp/pkhex/PKHeX.Core/PKHeX.Core.csproj > /tmp/forms.json
```

Then trim each species' list to its form count from `gen7-form-types.json` and wrap it with the source block, as in the committed file.
