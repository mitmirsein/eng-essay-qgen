import os
import re
import subprocess
from pathlib import Path

def process_files():
    q_dir = Path("output/essay-questions")
    lp_dir = Path("output/lesson-plans")
    
    for q_path in q_dir.glob("*.md"):
        content = q_path.read_text()
        
        # Check if it has "💡 교사용 모범 답안" or "📊 채점 기준"
        if "💡 교사용 모범 답안" not in content and "📊 채점 기준" not in content and "채점 기준" not in content:
            continue
            
        print(f"Fixing {q_path.name}...")
        
        # Split the content
        parts = re.split(r'---\s*\n+### 💡 교사용 모범 답안', content)
        if len(parts) < 2:
            parts = re.split(r'### 💡 교사용 모범 답안', content)
        
        if len(parts) == 2:
            student_part = parts[0].strip() + "\n"
            teacher_part = "### 💡 교사용 모범 답안" + parts[1]
        else:
            # Maybe it just has rubric
            parts = re.split(r'---\s*\n+### 📊 채점 기준', content)
            if len(parts) < 2:
                parts = re.split(r'### 📊 채점 기준', content)
            if len(parts) == 2:
                student_part = parts[0].strip() + "\n"
                teacher_part = "### 📊 채점 기준" + parts[1]
            else:
                print(f"Warning: Could not parse {q_path.name}")
                continue

        # Write fixed student part
        q_path.write_text(student_part)
        
        # Find corresponding lesson plan
        # 20260801_120100-type1-snow_white.md -> 20260801_120200-type1-snow_white_lesson.md
        # Time might differ by 1 minute, so match by type and subject
        base_name_match = re.search(r'-type\d+-(.+)\.md', q_path.name)
        if not base_name_match:
            continue
            
        subject = base_name_match.group(1)
        lp_path = None
        for p in lp_dir.glob(f"*-{subject}_lesson.md"):
            lp_path = p
            break
            
        if lp_path and lp_path.exists():
            lp_content = lp_path.read_text()
            if "채점 기준 및 배점표" not in lp_content and "📊 채점 기준" not in lp_content:
                # Insert teacher part before "### 5. 교사용 수업 스크립트" or at the end
                if "### 5. 교사용 수업 스크립트" in lp_content:
                    lp_content = lp_content.replace("### 5. 교사용 수업 스크립트", teacher_part.strip() + "\n\n### 6. 교사용 수업 스크립트")
                else:
                    lp_content += "\n\n" + teacher_part.strip() + "\n"
                lp_path.write_text(lp_content)
        
        # Regenerate PDFs
        subprocess.run(["python3", "tools/exam-pdf/make_exam_pdf.py", str(q_path), "--title", "영어 서술형 평가", "--subtitle", "중고등부 대비"])
        if lp_path:
            subprocess.run(["python3", "tools/exam-pdf/make_exam_pdf.py", str(lp_path), "--title", "교사용 수업 지도안", "--subtitle", "영어 서술형 대비"])

if __name__ == "__main__":
    process_files()
