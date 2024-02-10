import timeit
import pickle
import json
import yaml
from asteval import Interpreter
import hissbytenotation as hbn
import test.generate as generator

data = generator.generate_test_data(no_bytes=True, no_sets=True, no_elipsis=True)

aeval = Interpreter(minimal=True)

def benchmark_just_repr():
    # load
    repr_string = repr(data)

def benchmark_asteval():
    # load
    repr_string = repr(data)
    _result = aeval(repr_string)


def benchmark_hbn_no_validate_exec():
    serialized = hbn.dumps(data, validate=False)
    hbn.loads(serialized, by_exec=True)


def benchmark_hbn_no_validate_by_import():
    serialized = hbn.dumps(data, validate=False)
    hbn.loads(serialized, by_import=True)


def benchmark_hbn_no_validate_by_eval():
    serialized = hbn.dumps(data, validate=False)
    hbn.loads(serialized, by_eval=True)


def benchmark_hbn_no_validate():
    serialized = hbn.dumps(data, validate=False)
    hbn.loads(serialized)


def benchmark_hbn_validate():
    serialized = hbn.dumps(data, validate=True)
    hbn.loads(serialized)


def benchmark_pickle():
    serialized = pickle.dumps(data)
    pickle.loads(serialized)


def benchmark_json():
    serialized = json.dumps(data)
    json.loads(serialized)


def benchmark_yaml():
    # try:
    serialized = yaml.dump(data, default_flow_style=False)
    # except Exception as E:
    #     raise E

    yaml.load(serialized, Loader=yaml.FullLoader)

count=1000

pickle_time = timeit.timeit(benchmark_pickle, number=count)
json_time = timeit.timeit(benchmark_json, number=count)
# can't represent a lot?
# yaml_time = timeit.timeit(benchmark_yaml, number=count)
hbn_time_no_validate = timeit.timeit(benchmark_hbn_no_validate, number=count)
hbn_time_validate = timeit.timeit(benchmark_hbn_validate, number=count)
hbn_time_by_eval = timeit.timeit(benchmark_hbn_no_validate_by_eval, number=count)
hbn_time_exec = timeit.timeit(benchmark_hbn_no_validate_exec, number=count)
hbn_time_by_import = timeit.timeit(benchmark_hbn_no_validate_by_import, number=count)

repr_time = timeit.timeit(benchmark_just_repr, number=count)
asteval_time = timeit.timeit(benchmark_asteval, number=count)

print(f"## Serialization and deserialization times for {count} dumps/loads")
print(f"Oneway repr {repr_time:.2f} seconds")
print(f"Pickle:  {pickle_time:.2f} seconds")
print(f"JSON: {json_time:.2f} seconds")
print(f"asteval (repr + Interpreter()):  {asteval_time:.2f} seconds")
# print(f"YAML serialization and deserialization time: {yaml_time:.2f} seconds")
print(f"HBN (repr + ast_eval, no validation): {hbn_time_no_validate:.2f} seconds")
print(f"HBN (repr + ast_eval + validation): {hbn_time_validate:.2f} seconds")
print(f"HBN (repr + eval): {hbn_time_by_eval:.2f} seconds")
print(f"HBN (repr + exec): {hbn_time_exec:.2f} seconds")
print(f"HBN (repr + by import): {hbn_time_by_import:.2f} seconds")
