import csv, json

with open("data/temperature.csv", newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

temps = [float(r["temperature"]) for r in rows]
count = len(temps)
mean = sum(temps) / count
mx = max(temps)
mn = min(temps)

result = {"count": count, "mean": mean, "max": mx, "min": mn}
with open("result.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

report = (
    "# 温度分析报告\n\n"
    "- 样本数: {count}\n"
    "- 平均温度: {mean:.2f} °C\n"
    "- 最高温度: {mx:.2f} °C\n"
    "- 最低温度: {mn:.2f} °C\n"
    "- 温度单位: °C\n"
).format(count=count, mean=mean, mx=mx, mn=mn)

with open("report.md", "w", encoding="utf-8") as f:
    f.write(report)

print(json.dumps(result, ensure_ascii=False))
