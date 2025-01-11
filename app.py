from flask import Flask, request, render_template, send_from_directory, redirect, url_for, send_file
import os
import shutil  # 添加shutil模块用于删除文件夹
import zipfile  # 添加zipfile模块用于创建zip文件
import tempfile  # 添加tempfile模块用于创建临时文件
import mimetypes  # 添加mimetypes模块用于判断文件类型

# 添加更多视频格式的 MIME 类型
mimetypes.add_type('application/x-mpegURL', '.m3u8')
mimetypes.add_type('video/MP2T', '.ts')
mimetypes.add_type('video/vnd.dlna.mpeg-tts', '.ts')
mimetypes.add_type('video/mpeg', '.ts')

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024  # 2GB max file size

# 确保上传文件夹存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def is_previewable(filename):
    """判断文件是否可以预览"""
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type:
        return mime_type.startswith(('text/', 'image/', 'application/pdf', 'audio/', 'video/'))
    return False

def get_file_content(filepath, max_size=100000):
    """获取文件内容，限制大小以防止内存溢出"""
    try:
        if os.path.getsize(filepath) > max_size:
            return None
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except (UnicodeDecodeError, IOError):
        return None

@app.route('/')
def index():
    files = []
    for root, dirs, filenames in os.walk(app.config['UPLOAD_FOLDER']):
        for filename in filenames:
            # 获取相对于上传文件夹的路径
            rel_dir = os.path.relpath(root, app.config['UPLOAD_FOLDER'])
            if rel_dir == '.':
                files.append(filename)
            else:
                files.append(os.path.join(rel_dir, filename).replace('\\', '/'))
    return render_template('index.html', files=files)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(request.url)
    
    files = request.files.getlist('file')
    for file in files:
        if file.filename == '':
            continue
        
        # 处理文件夹路径
        filepath = file.filename.replace('\\', '/')
        directory = os.path.dirname(filepath)
        
        if directory:
            # 创建目录
            full_directory = os.path.join(app.config['UPLOAD_FOLDER'], directory)
            os.makedirs(full_directory, exist_ok=True)
        
        # 保存文件
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], filepath)
        file.save(full_path)
    
    return redirect(url_for('index'))

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        filename,
        as_attachment=True  # 这将强制浏览器下载文件而不是显示
    )

@app.route('/download_all')
def download_all():
    # 创建一个临时文件来存储zip
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
    temp_file.close()

    try:
        # 创建zip文件
        with zipfile.ZipFile(temp_file.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(app.config['UPLOAD_FOLDER']):
                for file in files:
                    file_path = os.path.join(root, file)
                    # 获取相对于upload文件夹的路径
                    arc_name = os.path.relpath(file_path, app.config['UPLOAD_FOLDER'])
                    zipf.write(file_path, arc_name)

        # 发送zip文件
        return send_file(
            temp_file.name,
            as_attachment=True,
            download_name='all_files.zip'
        )
    except Exception as e:
        print(f"Error creating zip file: {e}")
        return "创建压缩文件时出错", 500
    finally:
        # 确保在发送后删除临时文件
        try:
            os.unlink(temp_file.name)
        except:
            pass

@app.route('/delete_all', methods=['POST'])
def delete_all():
    try:
        # 删除uploads文件夹及其所有内容
        shutil.rmtree(app.config['UPLOAD_FOLDER'])
        # 重新创建空的uploads文件夹
        os.makedirs(app.config['UPLOAD_FOLDER'])
        return redirect(url_for('index'))
    except Exception as e:
        print(f"Error deleting files: {e}")
        return "删除文件时出错", 500

@app.route('/preview/<path:filename>')
def preview_file(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(filepath):
        return "文件不存在", 404
        
    mime_type, _ = mimetypes.guess_type(filename)
    
    # 如果是图片，直接显示
    if mime_type and mime_type.startswith('image/'):
        return send_file(filepath)
    
    # 如果是文本文件，读取内容
    if mime_type and mime_type.startswith('text/'):
        content = get_file_content(filepath)
        if content is not None:
            return render_template('preview.html', 
                                filename=filename,
                                content=content,
                                file_type='text')
    
    # 如果是PDF，提供嵌入式预览
    if mime_type == 'application/pdf':
        return render_template('preview.html',
                             filename=filename,
                             file_path=url_for('download_file', filename=filename),
                             file_type='pdf')
    
    # 如果是音频文件
    if mime_type and mime_type.startswith('audio/'):
        return render_template('preview.html',
                             filename=filename,
                             file_path=url_for('download_file', filename=filename),
                             file_type='audio',
                             mime_type=mime_type)
    
    # 如果是视频文件或TS流
    if (mime_type and mime_type.startswith('video/')) or \
       (filename.lower().endswith('.ts')) or \
       (mime_type and mime_type in ['application/x-mpegURL']):
        return render_template('preview.html',
                             filename=filename,
                             file_path=url_for('download_file', filename=filename),
                             file_type='video',
                             mime_type=mime_type if mime_type else 'video/MP2T')
    
    return "此文件类型不支持预览", 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
