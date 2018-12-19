from time import sleep
from urllib.request import urlopen
from sys import exit
from espeakng import ESpeakNG
def internet_on():
    try:
        urlopen('http://216.58.192.142', timeout=1)
        return True
    except Exception as e:
        print(e)
        return False

esng = ESpeakNG()
esng.voice = 'korean'
esng.say("시스템 초기화 중입니다. 약 이십초 정도 걸립니다.")
i = 0
while i<20:
    print('Waiting for WIFI(',i+1,"s/20s)", sep='', end='\r')
    sleep(1)
    i += 1
try:
    if internet_on():
        from actions import say
        print("Loading online script...")
        say("인공지능 서버와 연결중입니다")
        from online import main
    else:
        esng.say("인공지능 서버와 연결할 수 없습니다. 오프라인 모드로 전환합니다.")
        print("Loading offline script...")
        from offline import main
except Exception as e:
    print(e)
    try:
        print("Error occured while importing. try to load offline script...")
        from offline import main
    except Exception as e:
        print(e)
        exit("Cannot import voice script")

main()
