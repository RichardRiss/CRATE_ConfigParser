import PyInstaller.__main__

PyInstaller.__main__.run([
    'main.py',
    '--onefile',
    '--noconsole',
    '--icon=desy.ico',
    '-n ConfigParser_LINAC',
    '--clean'
])
