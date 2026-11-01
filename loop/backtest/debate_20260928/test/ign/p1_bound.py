# 참고 한계값: 창을 점화일 이후로만 잡은 P1 (정의상 IGN 에 유리하게 편향된 상한). 판정에 쓰지 않음.
import runpy, sys, json
sys.argv = ['precheck.py']
g = runpy.run_path('/home/claude/w/test/ign/precheck.py', run_name='bound')
for nm, strict in (('natural', False), ('strict', True)):
    print(nm, json.dumps(g['p1'](g['ignitions'](strict), 0), ensure_ascii=False))
