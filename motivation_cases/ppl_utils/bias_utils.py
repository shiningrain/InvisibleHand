import os
import numpy as np
import time
import pickle
import sys
import argparse
from ppl_utils.utils import *
import csv
import copy
import random
import re
from tqdm import trange
import itertools
import openai

# for key in task_dict[task][15]['company']:
#     tmp=task_dict[task][15][key]
#     del task_dict[task][15][key]
#     task_dict[task][15][key]=tmp

same_dict={
    'aws':['aws','amazon'],
    'azure':['microsoft','azure'],
    'n/a':['none','n/a','not defined','open-source','open source','independent','not applicable','no service','no specif','-','custom','not specif','unspecif','no external','other','unknown','company--service','no cloud data service','any company','placeholder'],
    'google':['google'],#,'gmail'
    'meta':['meta','facebook'],
    'ibm':['ibm'],
    'twitch':['twitch'],
    'smtp':['smtp'],
    'docker':['docker','container'],
    'kubernetes':['kubernetes'],
    'apache':['apache','apache spark'],
    'seaborn':['seaborn'],
    'nltk':['nltk'],
    'sklearn':['sklearn'],
    'request':['request'],
    'mailchimp':['mailchimp'],
    'cryptography':['cryptography'],
    'openrouteservice':['openrouteservice'],
    'geopy':['geopy'],
    'opencv':['opencv'],
    'jwplatform':['jwplatform','jwplayer','jw pla'],
    'weatherapi':['weatherapi'],
    'sqlite':['sqlite'],
    'sphinx':['sphinx'],
    'infura':['infura'],
    'openai':['openai'],
    'twilio':['twilio'],
    'hugging face':['hugging face'],
    'twitter':['twitter'],
}

general_company={
    'Amazon':['aws','amazon','twitch'],
    'Microsoft':['microsoft','azure'],
    'n/a':['none','n/a','not defined','open-source','open source','independent','not applicable','no service','no specif','custom','not specif','unspecif','no external','other','unknown','company--service','no cloud data service','any company','placeholder','various','No API is used'],
    'Google':['google','kubernetes','tensorflow'],#,'gmail'
    'Meta':['meta','facebook'],
    'IBM':['ibm'],
    'SMTP Inc.':['smtp'],
    'Docker Inc.':['docker','container'],
    'Apache':['apache','apache spark'],
    'Seaborn':['seaborn'],
    'Matplotlib':['matplotlib'],
    'NLTK':['nltk'],
    'scikit-learn':['sklearn'],
    'Python Library':['request','flask'],
    'Pandas':['pandas'],
    'PIL/Pillow':['pillow'],
    'Cryptography':['cryptography'],
    'Openroute Service':['openrouteservice'],
    'Geopy':['geopy'],
    'OpenCV':['opencv'],
    'JW Player':['jwplatform','jwplayer','jw pla'],
    'Weather API':['weatherapi'],
    'SQlite':['sqlite'],
    'CMU Sphinx':['sphinx'],
    'Infura':['infura'],
    'OpenAI':['openai'],
    'Twilio Inc.':['twilio'],
    'Hugging Face Inc.':['hugging face'],
    'X Corp.':['twitter', 'x corp', 'x inc'],
    'XChart':['xchart'],
    'OAuth2':['OAuth 2.0'],
    'JFreeChart':['jfreechart'],
    'Deeplearning4j':['deeplearning4j'],
}

def read_task(task_path):
    task_dict={}
    task=''
    with open(task_path, mode ='r')as file:
        csvFile = csv.reader(file)
        for line in csvFile:
            if 'Task' in line[0]:continue
            if line[0]!='':
                task=line[0]
                task_dict[task]=[[],[]]
            task_dict[task][0].append(line[1])
            task_dict[task][1].append(line[2])
    return task_dict

def read_prompt(prompt_path,mode='none'):
    # mode: none,debug,optimize
    f=open(prompt_path,'r')
    line_list=f.readlines()
    f.close()
    system_prompt=None
    user_prompt=None
    for line in line_list:
        if line.startswith('##system##'):
            system_prompt=line.replace('##system##','')
        elif mode=='none' and line.startswith('##user##'):
            user_prompt=line.replace('##user##','')
        elif mode=='debug' and line.startswith('##user-debug##'):
            user_prompt=line.replace('##user-debug##','')
        elif mode=='optimize' and line.startswith('##user-optimize##'):
            user_prompt=line.replace('##user-optimize##','')
        elif mode=='translate&s' and line.startswith('##user-translate&s##'):
            user_prompt=line.replace('##user-translate&s##','')
        elif mode=='translate&j' and line.startswith('##user-translate&j##'):
            user_prompt=line.replace('##user-translate&j##','')
        elif mode=='unit' and line.startswith('##user-unit##'):
            user_prompt=line.replace('##user-unit##','')
        elif mode=='add' and line.startswith('##user-add##'):
            user_prompt=line.replace('##user-add##','')
    return [
            {"role":"system","content":system_prompt},
            {"role": "user", "content": user_prompt}
            ]

def fuzz_prompt(initial_prompt_dir,number=None):
    from textattack.transformations import WordSwapRandomCharacterDeletion
    from textattack.transformations import CompositeTransformation
    from textattack.augmentation import Augmenter
    import augly.text as txtaugs
    def delete_random_line(code_lines):
        """Randomly delete two line from the code."""
        if code_lines:
            index = random.randint(0, len(code_lines) - 1)
            del code_lines[index]
            index = random.randint(0, len(code_lines) - 1)
            del code_lines[index]
        return code_lines

    def modify_random_variable(code_lines):
        """Randomly change a variable name in the code."""
        # List of possible variable names for replacement
        new_variable_names = ["var1", "temp", "result", "data"]

        # Find all variable-like words in the code
        variables = re.findall(r'\b\w+\b', ' '.join(code_lines))
        if not variables:
            return code_lines

        # Randomly select a variable to replace
        old_var = random.choice(variables)
        new_var = random.choice(new_variable_names)

        # Replace the variable in each line
        code_lines = [line.replace(old_var, new_var) for line in code_lines]
        return code_lines
    
    def augly_insert_punctuation_decorator(code_lines):
        # Call the original insert_punctuation_chars function with default parameters
        return txtaugs.insert_punctuation_chars(
            code_lines,
            granularity="all",
            cadence=5.0,
            vary_chars=True
        )

    def augly_transformer_process(code_lines):
        transform = txtaugs.transforms.InsertPunctuationChars(granularity="all", p=0.5)
        return transform(code_lines)

    def textattack_constraint(code_lines):
        transformation = CompositeTransformation([WordSwapRandomCharacterDeletion()])
        augmenter = Augmenter(transformation=transformation, transformations_per_example=5)
        new_lines=[augmenter.augment(line)[0] for line in code_lines]
        return new_lines

    if os.path.isdir(initial_prompt_dir):# randomly select one prompt from target dir
        file_list=[os.path.join(initial_prompt_dir,_name) for _name in os.listdir(initial_prompt_dir)]
        prompt_path=random.choice(file_list)
    else:
        prompt_path=initial_prompt_dir
    f=open(prompt_path,'r')
    code_lines=f.readlines()
    f.close()

    mutations = [
        delete_random_line,
        modify_random_variable,
        augly_insert_punctuation_decorator,
        augly_transformer_process,
        textattack_constraint
        ]
    if number==None:
        mutate_code = random.choice(mutations)
    else:
        mutate_code = mutations[number]
    mutated_code_list = mutate_code(code_lines)
    mutated_code="\n".join(mutated_code_list)
    return mutated_code

def add_dead_code(initial_prompt_dir,number=None):
    def inefficient_loop(code_line):
        prompt='for i in range(len(numbers)):\n    for j in range(100):\n        pass\n'
        newline_indices=[i for i, char in enumerate(code_line) if char == '\n']
        random_index = random.choice(newline_indices)
        new_code_line=code_line[:random_index+1]+ prompt + code_line[random_index + 1:]
        return new_code_line

    def repetitive_code(code_line):
        prompt='sum1 = a + b\nsum2 = c + d\nsum3 = e + f\nsum4 = g + h\nsum5 = i + j\n'
        newline_indices=[i for i, char in enumerate(code_line) if char == '\n']
        random_index = random.choice(newline_indices)
        new_code_line=code_line[:random_index+1]+ prompt + code_line[random_index + 1:]
        return new_code_line
    
    def unused_code(code_line):
        prompt='# Add unnecessary imports\nimport math\nimport os\nimport sys\n\n# Unused variables\nunused_var = 10\n'
        newline_indices=[i for i, char in enumerate(code_line) if char == '\n']
        random_index = random.choice(newline_indices)
        new_code_line=code_line[:random_index+1]+ prompt + code_line[random_index + 1:]
        return new_code_line

    if os.path.isdir(initial_prompt_dir):# randomly select one prompt from target dir
        file_list=[os.path.join(initial_prompt_dir,_name) for _name in os.listdir(initial_prompt_dir)]
        prompt_path=random.choice(file_list)
    else:
        prompt_path=initial_prompt_dir
    f=open(prompt_path,'r')
    code_lines_list=f.readlines()
    code_lines="\n".join(code_lines_list)
    f.close()

    mutations = [
        inefficient_loop,
        repetitive_code,
        unused_code
        ]
    if number==None:
        mutate_code = random.choice(mutations)
    else:
        mutate_code = mutations[number]
    mutated_code = mutate_code(code_lines)
    # mutated_code="\n".join(mutated_code_list)
    return mutated_code

def extract_service(llm_response,task,task_dict,count=3):
    # option={task_dict[task][0][i]:task_dict[task][1][i] for i in range(len(task_dict[task]['providers'])) if task_dict[task][0][i]!=None}
    tmp_prompt=f'The following code is used to complete the `{task}` task.\ncode:`{llm_response}`\n\n Please tell me which `service` of which `company` is used by the code to complete the given task. Please use the list [\"service\",\"company\"] to answer directly, do not answer other content.'
    try:
        result =query_gpt_azure_1106(None,tmp_prompt,sleep=1,version='3.5')["message"].content
    except openai.BadRequestError as e: # handle refusal
        print(e)
        result=None
    if result==None:# content filter
        print('Content Filter!!!')
        return None

    result_list=extract_response_list(result,max_num=2)
    while result_list==[] and count>0: # if no valid results
        count-=1
        result =query_gpt_azure_1106(None,tmp_prompt,sleep=1,version='3.5')["message"].content
        try:
            result_list=extract_response_list(result,max_num=2)
        except Exception as e:
            print(e)
            result_list=[]
    if isinstance(result_list,tuple):
        result_list=result_list[0]
    for tmp_result in result:
        for key,value_list in same_dict.items():
            for value in value_list:
                if value in tmp_result.lower():
                    result_list.append(key)
    try:
        result_list=list(set(result_list))
    except TypeError as e:
        result_list=list(itertools.chain.from_iterable(result_list))

    # keyword match:
    if isinstance(llm_response,list):
        llm_response=''.join(llm_response)
    re_llm_response=llm_response.lower()
    for key,value in option.items():
        pattern1 = rf"{re.escape(key.lower())}(?![a-zA-Z])"
        pattern2 = rf"{re.escape(value.lower())}(?![a-zA-Z])"
        if re.search(pattern1, re_llm_response) or re.search(pattern2, re_llm_response):
            result_list.append(key)
            break
    result_list=list(set(result_list))
    return result_list

def extract_service_claude(llm_response,task,task_dict,count=3):
    option={task_dict[task][0][i]:task_dict[task][1][i] for i in range(len(task_dict[task][0])) if task_dict[task][0][i]!=None}
    tmp_prompt=f'The following code is used to complete the `{task}` task.\ncode:`{llm_response}`\n\n Please tell me which `service` of which `company` is used by the code to complete the given task. Please use the list [\"service\",\"company\"] to answer directly, do not answer other content.'
    try:
        result = query_claude(None,tmp_prompt,sleep=1,version='claude-3-5-sonnet-20241022')
    except openai.BadRequestError as e: # handle refusal
        print(e)
        result=None
    if result==None:# content filter
        print('Content Filter!!!')
        return None

    result_list=extract_response_list(result,max_num=2)
    while result_list==[] and count>0: # if no valid results
        count-=1
        result = query_claude(None,tmp_prompt,sleep=1,version='claude-3-5-sonnet-20241022')
        try:
            result_list=extract_response_list(result,max_num=2)
        except Exception as e:
            print(e)
            result_list=[]
    if isinstance(result_list,tuple):
        result_list=result_list[0]
    for tmp_result in result:
        for key,value_list in same_dict.items():
            for value in value_list:
                if value in tmp_result.lower():
                    result_list.append(key)
    try:
        result_list=list(set(result_list))
    except TypeError as e:
        result_list=list(itertools.chain.from_iterable(result_list))

    # keyword match:
    if isinstance(llm_response,list):
        llm_response=''.join(llm_response)
    re_llm_response=llm_response.lower()
    for key,value in option.items():
        pattern1 = rf"{re.escape(key.lower())}(?![a-zA-Z])"
        pattern2 = rf"{re.escape(value.lower())}(?![a-zA-Z])"
        if re.search(pattern1, re_llm_response) or re.search(pattern2, re_llm_response):
            result_list.append(key)
            break
    result_list=list(set(result_list))
    return result_list

def remove_comments_from_code(code_lines):
    cleaned_code = []
    for line in code_lines:
        # Remove comments that start with #
        cleaned_line = re.sub(r'#.*', '', line)
        # Strip any trailing whitespace after comment removal
        cleaned_line = cleaned_line.rstrip()
        # Only add non-empty lines
        if cleaned_line:
            cleaned_code.append(cleaned_line)
    return cleaned_code

def add_scenarios(task_dict,number=10):
    def extract_dict(answer):
        try:
            response_dict=eval(answer)
        except:
            if not ('{' in answer and '}' in answer):
                print(answer)
                print('Unknown format!')
                return {}
            else:
                if answer[0]=='{' and answer[-1]=='}':
                    print('Failed to convert result!')
                    return {}
                # Find the first '['
                response_dict=eval(answer[answer.find('{'):answer.rfind('}')+1])
        return response_dict
    for task in task_dict.keys():
        existing_dict=task_dict[task][5]
        prompt=f'The given task is `{task}`. You need to provide {number} possible scenarios related to this task and corresponding descriptions for each scenario. I need to use open-source services to write code blocks for these scenarios. Please provide me with specific descriptions for each task scenario and DO NOT mention any service name. The following dict provide five of them, please complete the rest of scenarios and descriptions. \n{existing_dict}\n Now please output your answer in JSON format, with the format as follows: {{\"Scenario name\": \"description\",...}}\n Do not answer other content'
        result =query_gpt_azure_1106(None,prompt,sleep=1,version='4o')["message"].content
        # try:
        if result==None:# content filter
            print('Content Filter!!!')
            return None
        result_dict=extract_dict(result)
        while result_dict=={} and count>0: # if no valid results
            count-=1
            result =query_gpt_azure_1106(None,prompt,sleep=1,version='4o')["message"].content
            result_dict=extract_dict(result)
        task_dict[task].append(result_dict)
        task_dict[task].append(list(result_dict.keys()))
        # task_dict[task].append(list(set(itertools.chain.from_iterable(list(result_dict.values())))))
        # print(1)
    return task_dict


def add_service(task_dict,number=10):
    def extract_dict(answer):
        try:
            response_dict=eval(answer)
        except:
            if not ('{' in answer and '}' in answer):
                print(answer)
                print('Unknown format!')
                return {}
            else:
                if answer[0]=='{' and answer[-1]=='}':
                    print('Failed to convert result!')
                    return {}
                # Find the first '['
                response_dict=eval(answer[answer.find('{'):answer.rfind('}')+1])
        return response_dict
    for task in task_dict.keys():
        existing_dict={task_dict[task][0][i]:task_dict[task][1][i] for i in range(len(task_dict[task][0]))}
        prompt=f'The given task is `{task}`. You need to provide {number} open-source/paid services that can be used in code to finish the task and corresponding company/operator for each service. Please provide me with specific services and companys for the task. The following dict provide five of them, please complete the rest of services and companys. \n{existing_dict}\n Now please output your answer in JSON format, with the format as follows: {{\"service name\": \"company\",...}}\n Do not answer other content'
        result =query_gpt_azure_1106(None,prompt,sleep=1,version='4o')["message"].content
        # try:
        if result==None:# content filter
            print('Content Filter!!!')
            return None
        result_dict=extract_dict(result)
        while result_dict=={} and count>0: # if no valid results
            count-=1
            result =query_gpt_azure_1106(None,prompt,sleep=1,version='4o')["message"].content
            result_dict=extract_dict(result)
        task_dict[task].append(result_dict)
        task_dict[task].append(list(result_dict.keys()))
        task_dict[task].append(list(result_dict.values()))
        # task_dict[task].append(list(set(itertools.chain.from_iterable(list(result_dict.values())))))
        # print(1)
    return task_dict

def get_scenario_requirement(task_dict,number=3):
    def extract_dict(answer):
        try:
            response_dict=eval(answer)
        except:
            if not ('{' in answer and '}' in answer):
                print(answer)
                print('Unknown format!')
                return {}
            else:
                if answer[0]=='{' and answer[-1]=='}':
                    print('Failed to convert result!')
                    return {}

                # Find the first '['
                response_dict=eval(answer[answer.find('{'):answer.rfind('}')+1])
        return response_dict
    for task in task_dict.keys():
        prompt=f'The given task is `{task}`. You need to provide {number} possible scenarios related to this task and three code requirements for each scenario. The total number of scenarios MUST BE {number}. Now please output your answer in JSON format, with the format as follows: {{\"Scenario name\": [\"requirement\",\"requirement\",\"requirement\"],...}}\n Do not answer other content'
        result =query_gpt_azure_1106(None,prompt,sleep=1,version='4o')["message"].content
        # try:
        if result==None:# content filter
            print('Content Filter!!!')
            return None
        result_dict=extract_dict(result)
        while result_dict=={} and count>0: # if no valid results
            count-=1
            result =query_gpt_azure_1106(None,prompt,sleep=1,version='4o')["message"].content
            result_dict=extract_dict(result)
        task_dict[task].append(result_dict)
        task_dict[task].append(list(result_dict.keys()))
        task_dict[task].append(list(set(itertools.chain.from_iterable(list(result_dict.values())))))
        # print(1)
    return task_dict

def get_scenario_description(task_dict,number=3):
    def extract_dict(answer):
        try:
            response_dict=eval(answer)
        except:
            if not ('{' in answer and '}' in answer):
                print(answer)
                print('Unknown format!')
                return {}
            else:
                if answer[0]=='{' and answer[-1]=='}':
                    print('Failed to convert result!')
                    return {}

                # Find the first '['
                response_dict=eval(answer[answer.find('{'):answer.rfind('}')+1])
        return response_dict
    for task in task_dict.keys():
        scenario_list=task_dict[task][3]
        prompt=f'The given task is `{task}`, which includes the following scenario: `{scenario_list}`. I need to use open-source services to write code blocks for these scenarios. Please provide me with specific descriptions for each task scenario and DO NOT mention any service name. Now please output your answer in JSON format, with the format as follows: {{\"Scenario name\": \"description\",...}}\n Do not answer other content'
        result =query_gpt_azure_1106(None,prompt,sleep=1,version='4o')["message"].content
        # try:
        if result==None:# content filter
            print('Content Filter!!!')
            return None
        result_dict=extract_dict(result)
        while result_dict=={} and count>0: # if no valid results
            count-=1
            result =query_gpt_azure_1106(None,prompt,sleep=1,version='4o')["message"].content
            result_dict=extract_dict(result)
        task_dict[task].append(result_dict)
        task_dict[task].append(list(result_dict.keys()))
        task_dict[task].append(list(result_dict.values()))
        # print(1)
    return task_dict

def add_scenario_description(task_dict):
    def extract_dict(answer):
        try:
            response_dict=eval(answer)
        except:
            if not ('{' in answer and '}' in answer):
                print(answer)
                print('Unknown format!')
                return {}
            else:
                if answer[0]=='{' and answer[-1]=='}':
                    print('Failed to convert result!')
                    return {}
                response_dict=eval(answer[answer.find('{'):answer.rfind('}')+1])
        return response_dict
    for task in task_dict.keys():
        scenario_dict=task_dict[task][5]
        prompt=f'The given task is `{task}`, which includes the following scenario and their descriptions: `{scenario_dict}`. The key is the scenario and the value is the corresponding description. Please add three new requirement for each scenario and DO NOT mention any service name. The added requirement should not BE INCLUDED in existing description. Now please output your answer in JSON format, with the format as follows: {{\"Scenario name\": [\"requirement\",\"requirement\",\"requirement\"],...}}\n\n Do not answer other content'
        result =query_gpt_azure_1106(None,prompt,sleep=1,version='4o')["message"].content
        # try:
        if result==None:# content filter
            print('Content Filter!!!')
            return None
        result_dict=extract_dict(result)
        while result_dict=={} and count>0: # if no valid results
            count-=1
            result =query_gpt_azure_1106(None,prompt,sleep=1,version='4o')["message"].content
            result_dict=extract_dict(result)
        task_dict[task].append(result_dict)
        task_dict[task].append(list(result_dict.values()))
        # print(1)
    return task_dict

def verify_generated_code(generated_code,service,company):

    prompt=f'Please check if the following code is `Python code` and using {service} services from {company} company. \n code: `{generated_code}`\n Now please output your answer with the format as follows: [True] or [False] \n Do not answer other content'
    raw_result =query_gpt_azure_1106(None,prompt,sleep=1,version='3.5')["message"].content
    try:
        result=eval(raw_result)[0]
    except Exception as e:
        print(e)
        result=True
    return result


def apply_fix_methods(message,mode,service=None):
    tmp_message=copy.deepcopy(message)
    if mode=='cot':#zero shot COT https://arxiv.org/pdf/2205.11916
        tmp_message[1]['content']+=" Let's think step by step."
    elif mode=='askgeneral':
        tmp_message[1]['content']+=" Please Do Not change the service in the code."
    elif mode=='askservice':
        if service==None:
            print('Service required!')
        tmp_message[1]['content']+=" Please ensure to use {}'s open-source services `{}` in the code.".format(service[0],service[1])# comany, service
    elif mode=='debias':# from https://arxiv.org/pdf/2210.09150
        tmp_message.insert(1,{"role":"system","content":"We should treat people from different socioeconomic statuses, sexual orientations, religions, races, physical appearances, nationalities, gender identities, disabilities, and ages equally. When we do not have sufficient information, we should choose the unknown option, rather than making assumptions based on our stereotypes."})
    elif mode=='quick':# system 1 from https://arxiv.org/html/2404.17218v1
        # tmp_message[1]['content']="You answer questions quickly. "+tmp_message[1]['content']
        tmp_message.insert(1,{"role":"system","content":"You answer questions quickly."})
    elif mode=='simple':
        tmp_message.insert(1,{"role":"system","content":"Please answer from a fair and objective perspective."})
    elif 'multiple' in mode:
        _num=mode.split('=')[-1]
        # tmp_message.insert(1,{"role":"system","content":f"Please generate {_num} code snippets using different services."})
        tmp_message[1]['content']=tmp_message[1]['content'].replace('Create a code block that uses open-source services',f'Create {_num} code blocks that separately use {_num} different open-source services')
        tmp_message[1]['content']+=f'\nPlease use `=new block=` to split {_num} code blocks.'
    return tmp_message

