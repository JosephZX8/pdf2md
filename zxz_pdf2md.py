import os
import re
from typing import List, Tuple, Optional, Dict
import logging
import cv2
import requests
import json
import base64
import fitz
import shapely.geometry as sg
from shapely.geometry.base import BaseGeometry
from shapely.validation import explain_validity
import concurrent.futures
import numpy as np
from PIL import Image
from rapid_layout import RapidLayout, VisLayout

# 初始化日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 配置
API_URL = "https://api.siliconflow.cn/v1/chat/completions"
API_KEY = "sk-nifqlogntqslsqcyezypfgrpqswdhanjolubewmltwozukmz"

DEFAULT_PROMPT = """使用markdown语法，将图片中识别到的文字转换为markdown格式输出。你必须做到：
1. 输出和使用识别到的图片的相同的语言。
2. 不要解释和输出无关的文字。
3. 内容不要包含在```markdown ```中，段落公式使用 $$ $$，行内公式使用 $ $，忽略长直线和页码。
"""
DEFAULT_RECT_PROMPT = """图片中用带颜色的矩形框和名称(%s)标注出了一些区域。如果区域是表格或者图片，使用 ![]() 的形式插入到输出内容中，否则直接输出文字内容。"""
DEFAULT_ROLE_PROMPT = """你是一个PDF文档解析器，使用markdown和latex语法输出图片的内容。"""

# 初始化 rapid_layout
layout_engine = RapidLayout(model_type="pp_layout_cdla")


def _parse_pdf_to_images(pdf_path: str, output_dir: str = './output') -> List[Tuple[str, List[str]]]:
    image_infos = []
    pdf_document = fitz.open(pdf_path)
    for page_index, page in enumerate(pdf_document):
        rect_images = []
        logging.info(f'解析页面: {page_index}')
        pix = page.get_pixmap(matrix=fitz.Matrix(4, 4))
        pix = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
        boxes, scores, class_names, elapse = layout_engine(pix)
        
        for index, (class_name, box) in enumerate(zip(class_names, boxes)):
            if class_name in ['figure', 'table']:
                name = f'{page_index}_{index}.png'
                sub_pix = pix.crop(box)
                sub_pix.save(os.path.join(output_dir, name))
                rect_images.append(name)

        boxes_, scores_, class_names_ = [], [], []
        for i, (class_name, box, score) in enumerate(zip(class_names, boxes, scores)):
            if class_name in ['figure', 'table']:
                boxes_.append(box)
                scores_.append(score)
                class_names_.append(f'{page_index}_{i}.png')

        page_image = os.path.join(output_dir, f'{page_index}.png')
        pix_np = np.array(pix)
        pix_np = cv2.cvtColor(pix_np, cv2.COLOR_RGB2BGR)
        ploted_img = VisLayout.draw_detections(pix_np, boxes_, scores_, class_names_)
        if ploted_img is not None:
            cv2.imwrite(page_image, ploted_img)

        image_infos.append((page_image, rect_images))
    pdf_document.close()
    return image_infos


def _gpt_parse_images(
        image_infos: List[Tuple[str, List[str]]],
        prompt_dict: Optional[Dict] = None,
        output_dir: str = './',
        verbose: bool = False,
        gpt_worker: int = 1,
) -> str:
    if isinstance(prompt_dict, dict) and 'prompt' in prompt_dict:
        prompt = prompt_dict['prompt']
    else:
        prompt = DEFAULT_PROMPT

    if isinstance(prompt_dict, dict) and 'rect_prompt' in prompt_dict:
        rect_prompt = prompt_dict['rect_prompt']
    else:
        rect_prompt = DEFAULT_RECT_PROMPT

    if isinstance(prompt_dict, dict) and 'role_prompt' in prompt_dict:
        role_prompt = prompt_dict['role_prompt']
    else:
        role_prompt = DEFAULT_ROLE_PROMPT

    def _process_page(index: int, image_info: Tuple[str, List[str]]) -> Tuple[int, str]:
        logging.info(f'GPT解析页面: {index}')
        page_image, rect_images = image_info
        local_prompt = role_prompt + prompt
        if rect_images:
            local_prompt += rect_prompt % ', '.join(rect_images)

        with open(page_image, "rb") as image_file:
            image_base64 = base64.b64encode(image_file.read()).decode('utf-8')

        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "Qwen/Qwen2.5-VL-72B-Instruct",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_base64}"
                            }
                        },
                        {
                            "type": "text",
                            "text": local_prompt
                        }
                    ]
                }
            ],
            "max_tokens": 2000,
            "temperature": 0.7,
            "top_p": 0.9
        }
        try:
            response = requests.post(API_URL, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
            content = result['choices'][0]['message']['content']

            if '```markdown' in content:
                content = content.replace('```markdown\n', '')
                last_backticks_pos = content.rfind('```')
                if last_backticks_pos != -1:
                    content = content[:last_backticks_pos] + content[last_backticks_pos + 3:]

            return index, content
        except requests.exceptions.RequestException as e:
            logging.error(f"API请求失败: {str(e)}")
            return index, f"处理页面 {index} 时发生错误: {str(e)}"

    contents = [None] * len(image_infos)
    with concurrent.futures.ThreadPoolExecutor(max_workers=gpt_worker) as executor:
        futures = [executor.submit(_process_page, index, info) for index, info in enumerate(image_infos)]
        for future in concurrent.futures.as_completed(futures):
            index, content = future.result()
            contents[index] = content

    output_path = os.path.join(output_dir, 'output.md')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(contents))

    return '\n\n'.join(contents)


def parse_pdf(
        pdf_path: str,
        output_dir: str = './',
        prompt: Optional[Dict] = None,
        verbose: bool = False,
        gpt_worker: int = 1,
) -> Tuple[str, List[str]]:
    """
    Parse a PDF file into Markdown format.

    Returns:
    - content: Markdown文本内容
    - all_rect_images: 小图列表
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    image_infos = _parse_pdf_to_images(pdf_path, output_dir=output_dir)

    content = _gpt_parse_images(
        image_infos=image_infos,
        output_dir=output_dir,
        prompt_dict=prompt,
        verbose=verbose,
        gpt_worker=gpt_worker,
    )

    all_rect_images = []
    for page_image, rect_images in image_infos:
        if os.path.exists(page_image):
            os.remove(page_image)
        all_rect_images.extend(rect_images)

    return content, all_rect_images


# 只有自己单独运行 zxz_pdf2md.py 文件时才执行下面的测试
if __name__ == "__main__":
    test_pdf = 'test_zxz.pdf'
    output_dir = "./output"
    content, images = parse_pdf(
        pdf_path=test_pdf,
        output_dir=output_dir,
        verbose=True,
        gpt_worker=1
    )
    print(content)