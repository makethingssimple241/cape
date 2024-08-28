import importlib
import inspect
import os
import sys

class Recipe:
    def __init__(self, outputs):
        self.outputs = outputs
        self.is_ran = False

    def run(self):
        pass

class cc(Recipe):
    def __init__(self, **kwargs):
        self.outputs = [kwargs["output"]]
        self.kwargs = kwargs

    def run(self) -> int:
        cmd = "cc "

        match os.name:
            case 'posix':
                if self.kwargs["compile_only"]:
                    cmd += "-c "

                for input in self.kwargs["inputs"]:
                    cmd += f"{input} "

                if "defines" in self.kwargs:
                    for define in self.kwargs["defines"]:
                        cmd += f"-D {define} "

                if "include_dirs" in self.kwargs:
                    for dir in self.kwargs["include_dirs"]:
                        cmd += f"-I {dir} "
                
                if "library_dirs" in self.kwargs:
                    for dir in self.kwargs["library_dirs"]:
                        cmd += f"-L {dir} "

                if "libraries" in self.kwargs:
                    for lib in self.kwargs["libraries"]:
                        cmd += f"-l{lib} "

                if self.kwargs["symbols"]:
                    cmd += "-g "

                output = self.kwargs["output"]
                if output is not None:
                    cmd += f"-o {output}"
            case _:
                assert False

        return os.system(cmd)
    
class CapeError(Exception):
    def __init__(self, target, code = None):
        if code == 0:
            raise ValueError(f"Attempted to raise CapeError with success code {code}")
        
        message = f"cape: *** building '{target}' failed"
        if code is not None:
            message += f" with exit code {code}"

        super().__init__(message)
    
def wildcard(x):
    last_slash = x.rfind('/')
    base_path = ""
    if last_slash >= 0:
        base_path = x[:last_slash]
        wildcard =  x[last_slash + 1:]
    else:
        wildcard = x

    wildcard_count = wildcard.count('*')

    if wildcard_count not in range(1, 3):
        raise SyntaxError

    result = []
    
    for root, subdirectories, files in os.walk(base_path):
        for file in files:
            match wildcard_count:
                case 1:
                    if root == base_path:
                        asterisk_index = wildcard.find('*')
                        assert asterisk_index >= 0

                        prefix = wildcard[:asterisk_index]
                        suffix = wildcard[asterisk_index + 1:]

                        if file.startswith(prefix) and file.endswith(suffix):
                            result.append(os.path.join(root, file))
                case 2:
                    asterisk1 = wildcard.find('*')
                    asterisk2 = wildcard.rfind('*')
                    assert asterisk1 >= 0 and asterisk2 >= 0

                    prefix = wildcard[:asterisk1]
                    middle = wildcard[asterisk1 + 1:asterisk2]
                    suffix = wildcard[asterisk2 + 1:]

                    if file.startswith(prefix) and middle in file and file.endswith(suffix):
                        result.append(os.path.join(root, file))
                case _:
                    assert False

    return result

def target_up_to_date(expanded_prerequesties, outputs):
    for prerequisite in expanded_prerequesties:
        prerequisite_mtime = os.path.getmtime(prerequisite)

        for output in outputs:
            if not os.path.exists(output):
                return False

            output_mtime = os.path.getmtime(output)
            if prerequisite_mtime > output_mtime:
                return False
            
    return True

def target(*prerequesties):
    def decorator(recipe_factory):
        def make():
            expanded_prerequesties = []

            for prerequisite in prerequesties:
                if type(prerequisite) is str:
                    if prerequisite.find('*') >= 0:
                        expanded_prerequesties += wildcard(prerequisite)
                    else:
                        expanded_prerequesties.append(prerequisite)
                elif callable(type(prerequisite)) and hasattr(prerequisite, "is_cape_target") and prerequisite.is_cape_target:
                    outputs = prerequisite()
                    expanded_prerequesties += outputs
                else:
                    raise ValueError(f"Invalid prerequisite type {type(prerequisite)}")

            target_name = recipe_factory.__name__
            recipe = recipe_factory(target_name, expanded_prerequesties)

            if target_up_to_date(expanded_prerequesties, recipe.outputs):
                print(f"cape: '{target_name}' is up to date.")
            else:
                exit_code = recipe.run()
                if exit_code != 0:
                    raise CapeError(target_name, exit_code)
                
            return recipe.outputs

        make.is_cape_target = True
        return make
    return decorator

if __name__ == "__main__":
    importlib.import_module("build")
    functions = inspect.getmembers(sys.modules["build"], inspect.isfunction)
    targets = [function for name, function in functions if hasattr(function, "is_cape_target") and function.is_cape_target]

    try:
        for target in targets:
            target()
    except Exception as e:
        print(str(e))
        print("cape: *** terminating")
        exit(1)