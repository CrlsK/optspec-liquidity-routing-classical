"""QCentroid test runner."""
import json, sys
if __name__ == '__main__':
    f = sys.argv[1] if len(sys.argv) > 1 else 'input.json'
    with open(f) as fp: dic = json.load(fp)
    import qcentroid
    print(json.dumps(qcentroid.run(dic['data'], dic.get('solver_params', {}), dic.get('extra_arguments', {})), indent=2, default=str))
