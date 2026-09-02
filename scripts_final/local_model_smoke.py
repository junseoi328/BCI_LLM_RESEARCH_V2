from local_ft.inference import LocalBCIGenerator
def main():
    m=LocalBCIGenerator()
    for x in ["ㅁㅈ","ㄷㅇㅈ","ㅂㄲㅈ","ㅈㅅㅂㄲㅈ","ㄱㅁㅇ","ㅇㅍ"]:
        print("="*70); print(x,"=>",m.generate(x,16))
if __name__=="__main__": main()
