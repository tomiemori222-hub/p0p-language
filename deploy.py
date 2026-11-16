import os
import subprocess
import sys

REPO_NAME = "p0p-language"
GITHUB_YML = """name: Build Drink Runtime (DRE)
on: [push]
jobs:
  build:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        include:
          - os: windows-latest
            out_name: DrinkRuntimeEnvironment.exe
          - os: ubuntu-latest
            out_name: DrinkRuntimeEnvironment-linux
          - os: macos-latest
            out_name: DrinkRuntimeEnvironment-mac
    steps:
    - uses: actions/checkout@v4
    - run: gcc drink_vm.c -o ${{ matrix.out_name }} -static
    - uses: actions/upload-artifact@v4
      with:
        name: DRE-${{ matrix.os }}
        path: ${{ matrix.out_name }}
"""

def run_cmd(cmd):
    print(f"[*] Выполняю: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[ERROR] Ошибка: {result.stderr}")
        return False
    return True

def main():
    print("🫧 Подготовка к деплою p0P на GitHub...")

    # --- АВТОНАСТРОЙКА GIT ---
    # Проверяем, настроен ли Git, если нет - настраиваем
    check_git = subprocess.run("git config --get user.name", shell=True, capture_output=True, text=True)
    if not check_git.stdout.strip():
        print("[*] Git не настроен. Устанавливаю базовые настройки...")
        run_cmd('git config --global user.name "Logiloom"')
        run_cmd('git config --global user.email "logiloom@example.com"')

    # 1. Создаем папку для GitHub Actions
    os.makedirs(".github/workflows", exist_ok=True)
    with open(".github/workflows/build.yml", "w", encoding="utf-8") as f:
        f.write(GITHUB_YML)

    # 2. Создаем .gitignore
    with open(".gitignore", "w", encoding="utf-8") as f:
        f.write("__pycache__/\n*.pyc\nbuilds/\n*.exe\n*.drink\n")

    # 3. Инициализируем Git
    if not run_cmd("git init"): return
    if not run_cmd("git add ."): return
    if not run_cmd('git commit -m "Initial p0P release: CLI, Compiler, IDE, and DRE"'): return

    # 4. Создаем репозиторий на GitHub и пушим туда код
    print(f"\n[*] Создаю репозиторий '{REPO_NAME}' на GitHub...")
    if not run_cmd(f"gh repo create {REPO_NAME} --public --source=. --remote=origin --push"):
        print("[ERROR] Не удалось создать репозиторий. Убедись, что ты авторизован через 'gh auth login'")
        return

    print("\n✅ ГОТОВО! Код успешно залит на GitHub.")
    print("👉 Перейди в свой профиль на GitHub и проверь вкладку Actions — там уже должна идти сборка для Windows, Linux и Mac.")
    
    # 5. Опционально: удаление репозитория
    print("\n========================================")
    choice = input("Хочешь удалить репозиторий с GitHub? (y/n): ").lower()
    if choice == 'y':
        print("[*] Удаляю репозиторий...")
        run_cmd(f"gh repo delete {REPO_NAME} --yes")
        print("🗑️ Репозиторий удален с GitHub.")
    else:
        print("Репозиторий оставлен на GitHub.")

if __name__ == "__main__":
    main()