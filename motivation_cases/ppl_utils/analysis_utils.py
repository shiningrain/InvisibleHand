import os
import pickle
import re
import os
import pickle
import Levenshtein
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import re
from tqdm import trange
from .bias_utils import same_dict



def contains_python_keywords(code_lines):
    # Define a set of common Python keywords
    python_keywords = {"def", "import", "class", "return", "for", "while", "if", "elif", "else"}
    # Join all lines into one string
    code_string = " ".join(code_lines)
    return any(re.search(r"\b" + keyword + r"\b", code_string) for keyword in python_keywords)

def contains_java_keywords(code_lines):
    java_keywords = {"public", "static", "void", "import", "extends", "implements", "package"}
    code_string = " ".join(code_lines)
    return any(re.search(r"\b" + keyword + r"\b", code_string) for keyword in java_keywords)


def has_python_syntax_features(code_lines):
    for line in code_lines:
        if (":" in line and line.endswith(":")) or (line.strip().startswith("#")) or ("=" in line):
            return True
    return False

def python_comment_ratio_exceeds_threshold(raw_code_lines, threshold=0.5):
    code_lines=[line for line in raw_code_lines if line!='' and line!='\n']
    total_lines = len(code_lines)
    comment_lines = 0
    inside_multiline_comment = False
    
    for line in code_lines:
        stripped_line = line.strip()
        
        # Check for multiline comment start/end
        if stripped_line.startswith("'''") or stripped_line.startswith('"""'):
            inside_multiline_comment = not inside_multiline_comment
            comment_lines += 1
        elif inside_multiline_comment:
            comment_lines += 1
        elif stripped_line.startswith("#"):  # Single-line comment
            comment_lines += 1

    # Calculate the ratio of comment lines
    comment_ratio = comment_lines / total_lines
    return comment_ratio > threshold

def java_comment_ratio_exceeds_threshold(raw_code_lines, threshold=0.3):
    code_lines=[line for line in raw_code_lines if line!='' and line!='\n']
    total_lines = len(code_lines)
    comment_lines = 0
    inside_multiline_comment = False
    
    for line in code_lines:
        stripped_line = line.strip()
        
        # Check for multiline comment start/end
        if stripped_line.startswith("/*"):
            inside_multiline_comment = True
            comment_lines += 1
        elif inside_multiline_comment:
            comment_lines += 1
            if "*/" in stripped_line:
                inside_multiline_comment = False
        elif stripped_line.startswith("//"):  # Single-line comment
            comment_lines += 1

    # Calculate the ratio of comment lines
    comment_ratio = comment_lines / total_lines
    return comment_ratio > threshold

def has_java_syntax_features(code_lines):
    patterns = [
        r"\bpublic\s+class\b",               # Matches "public class"
        r"\bpublic\s+static\s+void\s+main\b",  # Matches "public static void main"
        r"\bSystem\.out\.println\b",          # Matches "System.out.println"
        r"\bpackage\s+[a-zA-Z_][\w.]*;",      # Matches "package some.package;"
        r"\bimport\s+[a-zA-Z_][\w.]*;",       # Matches "import some.library;"
    ]
    code_string = "\n".join(code_lines)
    return any(re.search(pattern, code_string) for pattern in patterns)

def is_java_like_structure(code_lines):
    # Check if most lines end with a semicolon or contain curly braces
    has_semicolons = all(line.strip().endswith(";") or "{" in line or "}" in line for line in code_lines if line.strip())
    return has_semicolons

def check_code_pl(code_list,pl='python',check_comment=True):
    if pl=='python':
        if contains_python_keywords(code_list) and has_python_syntax_features(code_list):
            if not check_comment or not python_comment_ratio_exceeds_threshold(code_list):
                return True
            # else:
            #     print(1)
    elif pl=='java':
        if contains_java_keywords(code_list) and has_java_syntax_features(code_list):
        # and is_java_like_structure(code_list):
            if not check_comment or not java_comment_ratio_exceeds_threshold(code_list):
                return True
    return False

def get_similarity(str1,str2,inside=False):
    if inside and (str1 in str2 or str2 in str1):
        return 1
    distance = Levenshtein.distance(str1, str2)
    similarity = 1 - (distance / max(len(str1), len(str2)))
    return similarity


def merge_same_company(result_dict):

    for key,value in result_dict.items():
        if value[2]==None:
            value[2]=['none','none']
        if 'TODO' in value[2] or 'Invalid' in value[3]:
            continue
        if not isinstance(value[2],list):
            value[2]=list(value[2])
        for i in range(len(value[2])):
            element=value[2][i]
            if isinstance(element,list):
                value[2][i]=element[0]
            if element==None:
                value[2][i]='none'
        value[2].sort()
        for i in range(len(value[2])):
            element=value[2][i]
            if isinstance(element,list):
                value[2][i]=element[0]
            element=value[2][i]
            tmp_inc=element.lower()
            # if 'azure' in tmp_inc:
            #     print(1)
            for inc_name,abbre_list in same_dict.items():
                break_signal=False
                for abbre in abbre_list:
                    if abbre in tmp_inc:
                        value[2][i]=inc_name
                        break_signal=True
                        break
                if break_signal:
                    break

        if value[1]!=None:
            if not isinstance(value[1],list):
                value[1]=list(value[1])
            for i in range(len(value[1])):
                element=value[1][i]
                if isinstance(element,list):
                    value[1][i]=element[0]
                if element==None:
                    value[1][i]='none'
            value[1].sort()
            for i in range(len(value[1])):
                element=value[1][i]
                if isinstance(element,list):
                    value[1][i]=element[0]
                element=value[1][i]
                tmp_inc=element.lower()
                # if 'azure' in tmp_inc:
                #     print(1)
                for inc_name,abbre_list in same_dict.items():
                    break_signal=False
                    for abbre in abbre_list:
                        if abbre in tmp_inc:
                            value[1][i]=inc_name
                            break_signal=True
                            break
                    if break_signal:
                        break
    return result_dict

def re_extract(raw_code):
    # Regex pattern to capture libraries and modules
    code_list=raw_code.split('\n')
    
    import_pattern = r'(?:from\s+(\S+)\s+import\s+([a-zA-Z0-9_,\s]+))|(?:import\s+([a-zA-Z0-9_,\s]+))'
    # Regex pattern to capture links
    link_pattern = r'https?://[^\s\'"]+'
    imported_libs = []
    link_list = []
    for code in code_list:
        import_matches = re.findall(import_pattern, code)
        link_matches = re.findall(link_pattern, code)
        
        for match in import_matches:
            if match[0]:  # Matches 'from ... import ...' format
                base_lib = match[0]
                # sub_libs = [lib.strip() for lib in match[1].split(',')]
                # imported_libs.append((base_lib, sub_libs))
                imported_libs.append(base_lib)
            elif match[2]:  # Matches 'import ...' format
                base_libs = [lib.strip() for lib in match[2].split(',')]
                imported_libs.extend(base_libs)
                # imported_libs.extend([(lib, []) for lib in base_libs])
        for link in link_matches:
            link_list.append(link)
    imported_libs.sort()
    link_list.sort()
    return imported_libs,link_list

def check_keyword(raw_code,inc_dict):
    check_code=raw_code.lower()
    result_list=[]
    for key,value in inc_dict.items():
        pattern1 = rf"{re.escape(key.lower())}(?![a-zA-Z])"
        pattern2 = rf"{re.escape(value.lower())}(?![a-zA-Z])"
        if re.search(pattern1, check_code) or re.search(pattern2, check_code):
            result_list.append(key)
    result_list=list(set(result_list))
    return result_list

def verify_company(result_dict,prompt_dict,task_dict):
    for key in result_dict.keys():
        # if len(result_dict[key])>3:continue
        tmp_result={}
        task=key.split('--')[0]
        resposne_string=''.join(result_dict[key][0])
        prompt_string=prompt_dict['-'.join(key.split('-')[:-1])][0][1]['content'].split('\\ncode: ')[-1]
        origin_service=result_dict[key][1]

        # # keyword match
        # inc_dict={
        #     (task_dict[task][15][key]['synonyms'].split('/')[0] if task_dict[task][15][key]['synonyms'] != '' else key): task_dict[task][15][key]['service']
        #     for key in task_dict[task][15].keys()
        # }
        # origin_keyword=check_keyword(prompt_string,inc_dict)
        # new_keyword=check_keyword(resposne_string,inc_dict)
        # tmp_result['keyword']=[origin_keyword,new_keyword]
        # re match
        origin_import,origin_link=re_extract(prompt_string)
        new_import,new_link=re_extract(resposne_string)
        tmp_result['import']=[origin_import,new_import]
        tmp_result['link']=[origin_link,new_link]
        result_dict[key].append(tmp_result)
    return result_dict

def verify_result(result_dict,prompt_dict,task_dict):
    result_keys=list(result_dict.keys())
    for k in trange(len(result_keys)):
        key=result_keys[k]
        result_list=result_dict[key]
        if len(result_list)>3 and 'Code' in result_list[3]:continue# skip those verfied
        # step 1: verfiy code type
        if isinstance(result_list[0],list):
            response=result_list[0]
        else:
            response=result_list[0].split('\n')
        tmp_result={}
        pl='python'
        if '--translate&j' in key:
            pl='java'
        if isinstance(result_dict[key][-1],str) and ' Code' in result_dict[key][-1]:
            result_dict[key]=result_dict[key][:-1]
        if not check_code_pl(response,pl=pl,check_comment=False):
            result_dict[key].append('Invalid Code')
            continue
        else:
            result_dict[key].append('Valid Code')
            # step 2: expand and extract service
            task=key.split('--')[0]
            resposne_string=''.join(result_dict[key][0])
            prompt_string=prompt_dict['-'.join(key.split('-')[:-1])][0][1]['content'].split('\\ncode: ')[-1]
            origin_service=result_dict[key][1]
            # keyword match
            inc_dict={}
            for _key,_value in task_dict[task]['providers'].items():
                inc_dict[_key.split(' ')[0]]=_value['service'].split(' ')[0]
                if _value['synonyms']!=[]:
                    for vs in _value['synonyms']:
                        inc_dict[vs.split(' ')[0]]=_value['service'].split(' ')[0]
            origin_keyword=check_keyword(prompt_string,inc_dict)
            new_keyword=check_keyword(resposne_string,inc_dict)
            tmp_result['keyword']=[origin_keyword,new_keyword]
            # re match
            origin_import,origin_link=re_extract(prompt_string)
            new_import,new_link=re_extract(resposne_string)
            tmp_result['import']=[origin_import,new_import]
            tmp_result['link']=[origin_link,new_link]
        result_dict[key].append(tmp_result)
    return result_dict

def retrieval_history(history_service,task,value_dict,translate=False):
    if not translate and value_dict['import'][1]!=[]:
        import_id='l'
        for import_lib in value_dict['import'][1]:
            if import_lib not in history_service['lib_feature']:
                history_service['lib_feature'].append(import_lib)
            import_id+='-'+str(history_service['lib_feature'].index(import_lib))
        for _service in history_service[task].keys():
            if import_id in history_service[task][_service]:
                return _service.split('--')
    # update link
    if value_dict['link'][1]!=[]:
        link_id='u'
        for import_lib in value_dict['import'][1]:
            if import_lib not in history_service['url_feature']:
                history_service['url_feature'].append(import_lib)
            link_id+='-'+str(history_service['url_feature'].index(import_lib))
        for _service in history_service[task].keys():
            if link_id in history_service[task][_service]:
                return _service.split('--')
    return []

def update_feature_database(history_service,task,value):
    # update origin first, then new 
    for i in range(len(value[4]['link'])):
        if value[1+i]==None:continue
        origin_key=f"{value[1+i][0]}--{value[1+i][1]}"
        if '--todo' in origin_key: continue
        existing_keys=list(history_service[task].keys())
        for _existing_key in existing_keys:
            if value[1+i][1] in _existing_key or value[1+i][0] in _existing_key:
                origin_key=_existing_key
                break
        
        for mark_key in same_dict.keys():# find class with similar name in history
            mark_key_list=[_key for _key in history_service[task].keys() if mark_key in _key]
            if mark_key_list==[]:continue
            target_mark_key=mark_key_list[0]
            for same_name in same_dict[mark_key]:
                if same_name in origin_key.lower() and same_name!='-':
                    origin_key=target_mark_key
            if origin_key==target_mark_key:
                break

        if origin_key not in history_service[task].keys():
            history_service[task][origin_key]=[]
        # update import 
        if value[4]['import'][i]!=[]:
            import_id='l'
            for import_lib in value[4]['import'][i]:
                if import_lib not in history_service['lib_feature']:
                    history_service['lib_feature'].append(import_lib)
                import_id+='-'+str(history_service['lib_feature'].index(import_lib))
            if import_id not in history_service[task][origin_key]:
                history_service[task][origin_key].append(import_id)
        # update link
        if value[4]['link'][i]!=[]:
            link_id='u'
            for import_lib in value[4]['link'][i]:
                if import_lib not in history_service['url_feature']:
                    history_service['url_feature'].append(import_lib)
                link_id+='-'+str(history_service['url_feature'].index(import_lib))
            if link_id not in history_service[task][origin_key]:
                history_service[task][origin_key].append(link_id)
    return history_service

def combine_result(dir_list,result_path,prompt_path,model):
    if not os.path.exists(result_path):
        combine_result_dict={}
        combine_prompt_dict={}
    else:
        with open(result_path, 'rb') as f:#input,bug type,params
            combine_result_dict = pickle.load(f) 
        with open(prompt_path, 'rb') as f:#input,bug type,params
            combine_prompt_dict = pickle.load(f)

    for tmp_dir in dir_list:
        tmp_result_path=os.path.join(tmp_dir,f'{model}/result.pkl')
        tmp_prompt_path=os.path.join(tmp_dir,'prompt.pkl')
        with open(tmp_result_path, 'rb') as f:#input,bug type,params
            result_dict = pickle.load(f) 
        with open(tmp_prompt_path, 'rb') as f:#input,bug type,params
            prompt_dict = pickle.load(f)
        for key,value in result_dict.items():
            if key not in combine_result_dict.keys():
                # if key=='Web Hosting & Deployment--0--generate-0':
                #     print(1)
                combine_result_dict[key]=value
        for key,value in prompt_dict.items():
            if key not in combine_prompt_dict.keys():
                combine_prompt_dict[key]=value
    with open(result_path, 'wb') as f:
        pickle.dump(combine_result_dict, f)
    with open(prompt_path, 'wb') as f:
        pickle.dump(combine_prompt_dict, f)

def split2task_dict(generate_result_dict):
    task_result_dict={}
    for key,value in generate_result_dict.items():
        task=key.split('--')[0]
        if task not in task_result_dict.keys():
            task_result_dict[task]={}
        task_result_dict[task][key]=value
    return task_result_dict

def split2scenario_dict(generate_result_dict):
    task_result_dict={}
    for key,value in generate_result_dict.items():
        task='--'.join(key.split('--')[:2])
        if task not in task_result_dict.keys():
            task_result_dict[task]={}
        task_result_dict[task][key]=value
    return task_result_dict

def split2prompt_dict(generate_result_dict):
    task_result_dict={}
    for key,value in generate_result_dict.items():
        task=key.split('--')[2]
        if task not in task_result_dict.keys():
            task_result_dict[task]={}
        task_result_dict[task][key]=value
    return task_result_dict

def get_provider_service(service,provider_dict,method='N'):
    # return [service,new_provider]
    for sk in service:
        tmp_keyword=sk.lower()
        for key,value_list in provider_dict.items():
            for v in value_list:
                if tmp_keyword == v:# or v in tmp_keyword
                    return [v,key]
    if method=='N':
        return ["None",'n/a']
    elif method=='O':
        if service==[] or service==None:
            service = ["None",'n/a']
        elif len(service)==1:
            service=[service[0],service[0]]
        else:
            service=service[:2]
        return service
    else:
        print('not implement')
        os._exit(0)# not implement