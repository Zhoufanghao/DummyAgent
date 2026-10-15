import os
from openai import OpenAI

client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com/beta")
response = client.completions.create(
    model="deepseek-flash", prompt="牛顿第二定律告诉我们，", max_tokens=12
)
print(response.choices[0].text)
