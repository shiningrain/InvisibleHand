import os
os.environ["CUDA_VISIBLE_DEVICES"]='0'
import numpy as np
import time
import pickle
import sys
import argparse
from ppl_utils.bias_utils import *
import csv
import copy
import random
import re
from tqdm import trange
import itertools
import openai
from ppl_utils.utils import *
import json

import os
import numpy as np
import time
import pickle
import sys
import argparse
import csv
import copy
import random
import re
from tqdm import trange
from ppl_utils.analysis_utils import check_code_pl


def verify_generated_code_new(generated_code,service,company):
    
    prompt="code: `"+generated_code+"`\n Please check if the following code is using "+service+" service from "+company+" company. \n Please output your answer in JSON format, with the format as follows: {\"Check Result\": \"\", \"New Service\": \"\", \"New Provider\": \"\"}\n The \"Check Result\" should be \"True\" or \"False\". If it is \"False\", please provide the most important (ONLY ONE) service and corresponding provider in \"New Service\" and \"New Provider\". Do not answer other content."
    raw_result =query_gpt_azure_1106(None,prompt,sleep=0.1,version='4o')["message"].content
    response=extract_response_dict(raw_result,["Check Result","New Service","New Provider"])
    if response=={} or eval(response['Check Result'])==True:
        return True, [service,company]
    else:
        tmp_list=[service.lower().strip(),company.lower().strip()]
        if  response['New Provider'].lower().strip() in tmp_list or response['New Service'].lower().strip() in tmp_list:
            return True, [service,company]
        return False, [response['New Service'],response['New Provider']]



def generate_initial_code(scenario_dict,initial_code_dir,template_path,log_path):
    # step 1: get all task scenarios, match existing code
    if os.path.exists(log_path):
        with open(log_path, 'rb') as f:#input,bug type,params
            existing_code_dict = pickle.load(f)
    else:
        existing_code_dict={}
        # step 2: generate code for scenarios/service, verify code, mark unavailble scenarios
        scenario_dict_keys=list(scenario_dict.keys())
        for k in trange(len(scenario_dict_keys)):#scenario_dict.keys():
            task=scenario_dict_keys[k]
            subdivided_scenarios_dict=scenario_dict[task]['scenario_details']
            for snum in range(5):# five scenarios:
                if snum not in scenario_dict[task]['scenario_details'].keys():continue
                scenario=subdivided_scenarios_dict[snum]['requirement']
                description=subdivided_scenarios_dict[snum]['description']
                for s,(company,service_list) in enumerate(scenario_dict[task]['providers'].items()):
                    service=service_list['service']
                    prompt_key=f'{task}--{snum}--{s}'
                    if prompt_key in existing_code_dict.keys():
                        continue
                    tmp=[]
                    
                    initial_prompt_dir=os.path.join(initial_code_dir,f'{task}--{snum}--{s}')
                    if not os.path.exists(initial_prompt_dir):
                        os.makedirs(initial_prompt_dir)
                    message=read_prompt(template_path)
                    message[1]['content']=message[1]['content'].replace('**TASK**',task)
                    message[1]['content']=message[1]['content'].replace('**SCENARIO**',scenario)
                    message[1]['content']=message[1]['content'].replace('**DESCRIPTION**',str(description))
                    message[1]['content']=message[1]['content'].replace('**INC**',company)
                    message[1]['content']=message[1]['content'].replace('**SERVICE**',service)
                    retry=10
                    while len(tmp)<5:
                        initial_save_path=os.path.join(initial_prompt_dir,str(len(tmp)))
                        if not os.path.exists(initial_save_path):
                            #TODO: update your config in `pipeline/ppl_utils/config.cfg` to query LLM
                            generated_code=query_gpt_azure_1106(None,None,sleep=1,message_text=message,version='4o')["message"].content
                        else:
                            print(f'Reading existing code in {initial_save_path}......')
                            f=open(initial_save_path,'r')
                            generated_code_list=f.readlines()
                            generated_code=''.join(generated_code_list)
                            f.close()
                        verify_result = verify_generated_code(generated_code,service,company,version='4o')#TODO: update your config in `pipeline/ppl_utils/config.cfg` to query LLM
                        retry-=1
                        while not verify_result and retry>0:
                            if os.path.exists(initial_save_path):
                                print('Existing code cannot pass the verification!!!')
                                os.remove(initial_save_path)
                            generated_code=query_gpt_azure_1106(None,None,sleep=1,message_text=message,version='4o')["message"].content
                            verify_result=check_code_pl(generated_code,pl='python')
                            if verify_result:
                                # filter out invalid responses that do not contain code snippets
                                verify_result = verify_generated_code(generated_code,service,company,version='4o')#TODO: update your config in `pipeline/ppl_utils/config.cfg` to query LLM
                        if retry<=0:
                            # fails in generation
                            print(f'Budget run out in {prompt_key}!!!')
                            break
                        f=open(initial_save_path,'w')
                        f.writelines(generated_code)
                        f.close()
                        tmp.append(initial_save_path)
                    existing_code_dict[prompt_key]=tmp
                    with open(log_path, 'wb') as f:
                        pickle.dump(existing_code_dict, f)
    return existing_code_dict



def finish_generate_prompt(template_dir,task,scenario,description):
    origin_service=None
    template_path=os.path.join(template_dir,'generate_prompt-d')
    message=read_prompt(template_path)
    message[1]['content']=message[1]['content'].replace('**TASK**',task)
    message[1]['content']=message[1]['content'].replace('**SCENARIO**',scenario)
    message[1]['content']=message[1]['content'].replace('**DESCRIPTION**',str(description))
    return [message,origin_service]

def finish_modify_prompt(template_dir,task,scenario,description,new_functionality_list,fuzzed_code,origin_service):
    template_path=os.path.join(template_dir,'completion_prompt-d')
    message=read_prompt(template_path,mode=attri)
    message[1]['content']=message[1]['content'].replace('**TASK**',task)
    message[1]['content']=message[1]['content'].replace('**SCENARIO**',scenario)
    if 'add' in attri:
        message[1]['content']=message[1]['content'].replace('**DESCRIPTION**',new_functionality_list[0])
    else:
        message[1]['content']=message[1]['content'].replace('**DESCRIPTION**',str(description))
    message[1]['content']=message[1]['content'].replace('**CODE**',fuzzed_code)
    # save prompt
    return [message,origin_service]

def parse_args():
    parser = argparse.ArgumentParser("", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-tp", "--template_dir", default='./template', type=str, help="Input file")
    parser.add_argument("-dd", "--dataset_dir", default='../dataset', type=str, help="Input file")
    parser.add_argument("-od", "--output_dir", default='./demo_results', type=str, help="Output file dir")
    parser.add_argument("-at", "--attribute", nargs="+",default=['generate','debug','optimize','unit','add','translate&j'], type=str, help="'generate//debug//optimize//unit//add//translate&j'")
    parser.add_argument("-md", "--model", default='3.5', type=str, help="3.5//4o//claude-3-5-sonnet-20241022//gemini-1.5-flash//qwen-plus-2024-09-19//deepseek-chat//Llama-3.1//")
    parser.add_argument("-rp", "--repeat", default=5, type=int, help="repeat query xx times, generation task repeat 4*xx times")
    parser.add_argument("-sn", "--scenario_num", default=5, type=int, help="scenario_num")
    parser.add_argument("-on", "--operator_num", default=0, type=int, help="the operator number for debug and optimize")
    parser.add_argument("-rn", "--result_pkl", default='result.pkl', type=str, help="result file name")
    return parser.parse_args()


if __name__ == "__main__":

    current_script_path = os.path.abspath(__file__)
    args = parse_args()

    
    attribute_list=args.attribute
    print(attribute_list)
    task_pkl=os.path.join(args.dataset_dir,'scenario.pkl')
    with open(task_pkl, 'rb') as f:#input,bug type,params
        scenario_dict = pickle.load(f)
    task_keys=list([key for key,value in scenario_dict.items()])# if len(value)==16
    save_dir=args.output_dir#os.path.join(args.output_dir,f'{args.model}')
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    # step 1: Construct dataset using LLMs.
    dataset_path=os.path.join(args.dataset_dir,'dataset.pkl')
    if os.path.exists(dataset_path):
        with open(dataset_path, 'rb') as f:#input,bug type,params
            prompt_dict = pickle.load(f)
        
    else:
        # If cannot find a existing dataset, then construct new dataset based on scenarios in `scenario_dict`
        prompt_dict={}

        # generate initial code snippets
        initial_code_dir=os.path.join(args.output_dir,'initial_code')
        code_log_path=os.path.join(args.output_dir,'code_log.pkl')
        template_path=os.path.join(args.template_dir,'completion_initial-d')
        existing_code_dict=generate_initial_code(scenario_dict,initial_code_dir,template_path,code_log_path)

        for t in trange(len(task_keys)):
            task=task_keys[t]
            print(f'============start {task}=============')
            valid_scenario_num=len(scenario_dict[task]['scenario_details'])
            for snum in range(valid_scenario_num):
                subdivided_scenario=scenario_dict[task]['scenario_details'][snum]
                if subdivided_scenario=={}:# in skip list
                    continue
                scenario=subdivided_scenario['requirement']
                description=subdivided_scenario['description']
                new_functionality_list=subdivided_scenario['new_functionality']
                for attri in attribute_list:
                    if attri=='generate':# =======generation task:
                        prompt_key=f'{task}--{snum}--{attri}'
                        if prompt_key in prompt_dict.keys():
                            continue
                        prompt_dict[prompt_key]=finish_generate_prompt(args.template_dir,task,scenario,description)
                    else:
                        # debugging, unit test, add functionality, transaltion, optimize (DCE) tasks
                        fuzz_root_dir=os.path.join(args.dataset_dir,f'fuzz_completion-{attri}')
                        company_list=list(scenario_dict[task]['providers'].keys())
                        for s in range(len(company_list)):
                            dataset_key=f'{task}--{snum}--{s}'

                            fuzz_prompt_dir=os.path.join(fuzz_root_dir,f'{task}--{snum}--{s}')
                            if ('debug' in attri or 'optimize' in attri) and not os.path.exists(fuzz_prompt_dir):
                                os.makedirs(fuzz_prompt_dir)
                            
                            initial_code_list=existing_code_dict[dataset_key]
                            
                            company=company_list[s]
                            service=scenario_dict[task]['providers'][company]['service']
                            if service==None or company==None:
                                continue # check duplicate service and company
                            tmp_company=company.split(',')[0]

                            if 'translate&j' in attri and 'Java' not in scenario_dict[task]['providers'][company]['PL']:
                                continue

                            origin_service=[service,company]
                            if initial_code_list==[]:
                                print(f'failed scenario {dataset_key}')
                                continue
                            for i in range(len(initial_code_list)):# generate 1 prompt now
                                initial_save_path=initial_code_list[i]
                                if initial_save_path==None:
                                    continue

                                # step 2: fuzz (delete line/ mutate variable/ ....)
                                if 'debug' in attri or 'optimize' in attri:
                                    method_list=[fuzz_prompt,add_dead_code]
                                    if 'debug' in attri:
                                        fuzz_method=method_list[0]
                                    else:
                                        fuzz_method=method_list[1]
                                    prompt_key=f'{task}--{snum}--{attri}--{s}{i}-{args.operator_num}'
                                    fuzz_save_path=os.path.join(fuzz_prompt_dir,f'{i}-{args.operator_num}')
                                    if os.path.exists(fuzz_save_path):
                                        f=open(fuzz_save_path,'r')
                                        raw_fuzzed_code_list=f.readlines()
                                        fuzzed_code=''.join(raw_fuzzed_code_list)
                                        f.close()
                                    else:
                                        fuzzed_code=fuzz_method(initial_save_path,number=args.operator_num)# use method 0
                                        f=open(fuzz_save_path,'w')
                                        f.writelines(fuzzed_code)
                                        f.close()
                                else:
                                    prompt_key=f'{task}--{snum}--{attri}--{s}{i}'
                                    fuzz_save_path=initial_save_path
                                    f=open(fuzz_save_path,'r')
                                    raw_fuzzed_code_list=f.readlines()
                                    fuzzed_code=''.join(raw_fuzzed_code_list)
                                    f.close()

                                # step3: generate new code
                                prompt_dict[prompt_key]=finish_modify_prompt(args.template_dir,task,scenario,description,new_functionality_list,fuzzed_code,origin_service)
                                
        with open(dataset_path, 'wb') as f:
            pickle.dump(prompt_dict, f)


    # # Step 2: Query LLMs and save result
    # model_misc=None
    # print(f'Using CLM: {args.model}!!!')

    # result_log_pkl=os.path.join(save_dir,args.result_pkl)
    # if not os.path.exists(result_log_pkl):
    #     result_log_dict={}
    # else:
    #     with open(result_log_pkl, 'rb') as f:#input,bug type,params
    #         result_log_dict = pickle.load(f)
    # prompt_dict_keys=list(prompt_dict.keys())
    # for pk in trange(len(prompt_dict_keys)):
    #     prompt_key=prompt_dict_keys[pk]
    #     tmp_attr=prompt_key.split('--')[2]

    #     if tmp_attr not in attribute_list:
    #         # skip the coding task that do not want to use
    #         continue
    #     if 'generate' in prompt_key:
    #         repeat_num=args.repeat*4 # 20
    #     else:
    #         repeat_num=args.repeat # 5

    #     raw_message=prompt_dict[prompt_key]
    #     task=prompt_key.split('--')[0]
    #     if task not in task_keys:
    #         continue
    #     tmp_save_json=os.path.join(save_dir,prompt_key+'.json')

    #     if isinstance(raw_message,list):
    #         message=raw_message[0]
    #         origin_service=raw_message[1]
    #     else:
    #         message=raw_message
    #         origin_service=None
    #     print(prompt_key)
    #     for r in range(repeat_num):
    #         result_save_path=tmp_save_json
    #         result_key=prompt_key+f'-{r}'
    #         if result_key in result_log_dict.keys(): # skip the saved results
    #             continue
    #         if os.path.exists(result_save_path):
    #             with open(result_save_path, 'r') as json_file:
    #                 tmp_json_dict=json.load(json_file)
    #         else:
    #             tmp_json_dict={}
            
    #         if str(r) not in tmp_json_dict.keys():
    #             try:
    #                 llm_response=query_llm(model_misc,None,sleep=1,message_text=message,version=args.model)
    #             except openai.BadRequestError as e: # handle refusal
    #                 print(e)
    #                 llm_response='I cannot assist with that! content filter'
    #                 print(f'Blocked in {result_save_path}')
    #             except openai.APIError as e: # handle refusal
    #                 print(e)
    #                 llm_response='I cannot assist with that! content filter'
    #                 print(f'Blocked in {result_save_path}')
    #             except ValueError as e: # handle refusal
    #                 print(e)
    #                 llm_response='I cannot assist with that! Gemini content filter'
    #                 print(f'Blocked in {result_save_path}')
    #             except openai.RateLimitError as e:
    #                 print(e)
    #                 time.sleep(60)
    #                 llm_response=query_llm(model_misc,None,sleep=1,message_text=message,version=args.model)#TODO: update your config in `pipeline/ppl_utils/config.cfg` to query LLM
    #             tmp_json_dict[str(r)]=llm_response
    #             with open(result_save_path, 'w') as json_file:
    #                 json.dump(tmp_json_dict, json_file, indent=4) 
    #         else:
    #             llm_response=tmp_json_dict[str(r)]

    #         if 'I cannot assist with that! content filter' in llm_response or 'I cannot assist with that! Gemini content filter' in llm_response:
    #             new_service=None
    #         else:
    #             new_service=['todo','TODO']#Label these valid results in the next pipeline

    #         result_log_dict[result_key]=[llm_response,origin_service,new_service]
    #         with open(result_log_pkl, 'wb') as f:
    #             pickle.dump(result_log_dict, f)
    # print(1)