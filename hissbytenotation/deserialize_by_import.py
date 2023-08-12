"""
Hack to load python source faster.
"""
import importlib.machinery
import importlib.util
from typing import Any


def loads_via_import(source_code: str) -> Any:
    """Write to file and import the module"""
    write_dict_to_file(source_code, "temp_dict_module.py")
    return reload_module("temp_dict_module", "temp_dict_module.py")


def write_dict_to_file(dict_str: str, file_path: str) -> None:
    """Just write to file"""
    with open(file_path, "w", encoding="utf-8") as file:
        file.write(f"data = {dict_str}")


def reload_module(module_name: str, file_path: str) -> Any:
    """Reload the module using importlib"""
    # pylint: disable=no-value-for-parameter
    # pylint: disable=deprecated-method
    loader = importlib.machinery.SourceFileLoader(module_name, file_path)
    module = loader.load_module()

    return module.data


# if __name__ == "__main__":
#     # Example usage
#     dict_str = "{'key1': 42, 'key2': 'value'}"
#     file_path = "temp_dict_module.py"
#     module_name = "temp_dict_module"
#
#     # Write the dictionary to the file and reload the module
#     write_dict_to_file(dict_str, file_path)
#     result_dict = reload_module(module_name, file_path)
#
#     print(result_dict)  # Output: {'key1': 42, 'key2': 'value'}
#
#     # Now let's modify the dictionary string and reload the module again
#     new_dict_str = "{'key3': [1, 2, 3], 'key4': 'new_value'}"
#     write_dict_to_file(new_dict_str, file_path)
#     result_dict = reload_module(module_name, file_path)
#
#     print(result_dict)  # Output: {'key3': [1, 2, 3], 'key4': 'new_value'}
