using PKHeX.Core;
var s = GameInfo.GetStrings("en");
var sb = new System.Text.StringBuilder("{");
for (ushort sp = 1; sp <= 807; sp++)
{
    var list = FormConverter.GetFormList(sp, s.types, s.forms, GameInfo.GenderSymbolASCII, EntityContext.Gen7);
    sb.Append(sp == 1 ? "" : ",").Append('"').Append(sp).Append("\":[");
    sb.Append(string.Join(",", list.Select(n => System.Text.Json.JsonSerializer.Serialize(n))));
    sb.Append(']');
}
sb.Append('}');
Console.WriteLine(sb.ToString());
