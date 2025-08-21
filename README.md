# DS_v2
cd "/Users/juyubin/Desktop/데이터 스토리텔링 대시보드"

# Git 초기화
git init

# 원격 저장소 연결 (본인 GitHub 계정으로 수정)
git remote add origin https://github.com/본인아이디/product-profit-dashboard.git

# 파일 추가
git add app.py requirements.txt KPI_Master_Small_12M_KR.csv

# 커밋
git commit -m "Add Streamlit dashboard with CSV"

# 푸시
git branch -M main
git push -u origin main
