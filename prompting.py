import openai
import os
from pydantic import BaseModel

openai_client = openai.Client(api_key=os.environ['OPENAI_API_KEY'])
COPYWRITER = "gpt-4o"


class ArticleDraft(BaseModel):
    title: str
    description: str
    content_markdown: str
    image_prompt: str


def complement_article(content: str) -> str:
    base_prompt = {
        "role":
        "system",
        "content":
        f"""Given a draft for an article, generate the title, meta description, the image prompt, and format the content in markdown (if not already done). You do not have discretion to change the content. If an H1 is included, remove it from the content, and use it for the title. Apply H2 headings for groupings/sections of paragrapghs.

        Generate a unique image prompt based on the article's content, but apply the base image style as described in BASE_IMAGE_STYLE.

[BASE_IMAGE_STYLE]
The image base style is washi watercolor wash; the images theme is to show a blend of nature and technology, whereas technology serves humanity and cares for nature. Show more nature, and very subtle technology... almost transparent, and servile. Dominant color is natural green and sky colors (blue for daylight, grey for stormy weather, twilight colors when appropriate). The images should convey a feeling of peace of mind, and a sense of calm.
[/BASE_IMAGE_STYLE]
"""
    }

    messages = [base_prompt, {"role": "user", "content": content}]
    response = openai_client.beta.chat.completions.parse(
        model=COPYWRITER, messages=messages, response_format=ArticleDraft)
    return response.choices[0].message.content


def generate_image(prompt: str):
    response = openai_client.images.generate(
        model="dall-e-3",
        prompt=prompt,
    )
    revised_prompt = response.data[0].revised_prompt
    img_url = response.data[0].url
    return {"img_url": img_url, "revised_prompt": revised_prompt}
