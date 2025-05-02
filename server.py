from flask import Flask, request, render_template, jsonify, send_from_directory
from flask_cors import CORS
import os
from zxz_pdf2md import parse_pdf

app = Flask(__name__, static_url_path='', static_folder='output')
CORS(app)  # 启用 CORS 支持

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

uploaded_pdf_path = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/parse')
def parse_page():
    return render_template('parse.html')

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Only PDF files are allowed'}), 400
    
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(file_path)

    try:
        # 调用 PDF 解析函数
        content, images = parse_pdf(
            pdf_path=file_path,
            output_dir=OUTPUT_FOLDER,
            verbose=True,
            gpt_worker=1
        )
        
        # 返回处理结果
        return jsonify({
            'success': True,
            'message': 'File processed successfully',
            'content': content,
            'images': images
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download/<filename>')
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)

@app.route('/api/status/<filename>')
def check_status(filename):
    md_path = os.path.join(OUTPUT_FOLDER, 'output.md')
    if os.path.exists(md_path):
        return jsonify({'status': 'completed'})
    return jsonify({'status': 'processing'})

# 新增提供 output 文件夹里的图片
@app.route('/output/<path:filename>')
def output_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)