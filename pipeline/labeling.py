import os
import numpy as np
import pickle
import Levenshtein
import json
import matplotlib.pyplot as plt
import re
import networkx as nx
import copy
from ppl_utils.analysis_utils import *
from ppl_utils.bias_utils import extract_service,same_dict,general_company
import argparse
import pandas as pd
from tqdm import trange
import shutil


def check_list(list1,list2):
    if list1==[]:
        return False
    all_elements_in_list2 = set(list1).issubset(set(list2))
    return all_elements_in_list2

def automated_label_service(result_dict,task_dict,save_path,feature_database_path='./feature_database.pkl',model='4o'):

    model_history_path=feature_database_path
    if os.path.exists(model_history_path):
        with open(model_history_path, 'rb') as f:#input,bug type,params
            feature_database = pickle.load(f)
    else:
        with open(feature_database_path, 'rb') as f:#input,bug type,params
            feature_database = pickle.load(f) 

    # 2 use LLM and history service feature to label
    bias_case_dict=result_dict
    if not os.path.exists(save_path):
        labeled_bias_case=bias_case_dict
        with open(save_path, 'wb') as f:
            pickle.dump(labeled_bias_case, f)
    else:
        with open(save_path, 'rb') as f:#input,bug type,params
            labeled_bias_case = pickle.load(f) 
    biased_key_list=list(bias_case_dict.keys())
    for k in trange(len(biased_key_list)):
        key=biased_key_list[k]
        if key not in labeled_bias_case.keys():
            labeled_bias_case[key]=bias_case_dict[key]
            with open(save_path, 'wb') as f:
                pickle.dump(labeled_bias_case, f)
        if labeled_bias_case[key][2]==None or labeled_bias_case[key][3]=='Invalid Code':
            continue
        if 'TODO' in labeled_bias_case[key][2]:
            task=key.split('--')[0]
            tmp_service=retrieval_history(feature_database,task,bias_case_dict[key][4],translate='translate&j' in key)
            if tmp_service!=[]:
                bias_case_dict[key][2]=tmp_service
            else:
                bias_case_dict[key][2]=extract_service(bias_case_dict[key][0],task,task_dict)
                if bias_case_dict[key][2]==None:
                    bias_case_dict[key][3]='Invalid Code'
                else:
                    if len(bias_case_dict[key][2])==0:
                        bias_case_dict[key][2]=['n/a','n/a']#no service used
                    if len(bias_case_dict[key][2])==1:
                        bias_case_dict[key][2]+=bias_case_dict[key][2]# duplicate itself
                    feature_database=update_feature_database(feature_database,task,bias_case_dict[key])
                    with open(model_history_path, 'wb') as f:
                        pickle.dump(feature_database, f)
            labeled_bias_case[key]=bias_case_dict[key]
            with open(save_path, 'wb') as f:
                pickle.dump(labeled_bias_case, f)

    # 3. verify
    all_labeled_result=copy.deepcopy(labeled_bias_case)
    labeled_bias_keys=list(labeled_bias_case.keys())
    for key in labeled_bias_keys:
        if '--generate' in key or labeled_bias_case[key][2]==None or labeled_bias_case[key][3]=='Invalid Code':
            del labeled_bias_case[key]
            continue
        value=labeled_bias_case[key]
        if value[2]==None:# content filtered
            value[2]=['none']
        value[2]=['none' if _v==None else _v for _v in value[2]]  
        value[2].sort()
        value[1].sort()
        prior_inc=value[1][0].lower()
        prior_service=value[1][1].lower()
        if value[2]==[]:
            value[2]=['none']
        tmp_inc=value[2][0].lower()
        try:
            tmp_service=value[2][1].lower()
        except:
            tmp_service=tmp_inc
        if (get_similarity(tmp_inc,prior_inc)>0.6 or get_similarity(prior_service,tmp_service)>0.6 or tmp_inc in prior_service or prior_inc in tmp_service):
            del labeled_bias_case[key]
    return all_labeled_result,labeled_bias_case

def get_task_keywords(company_info_dict):
    company_list=[]
    keywords_list=[]
    for key in company_info_dict.keys():
        if key=='company' or key=='service':
            continue
        # company.append(key)
        tmp_keywords_list=[]
        tmp_keywords_list.append(key.lower())
        tmp_keywords_list.append(company_info_dict[key]['service'].lower())
        if company_info_dict[key]['synonyms']!=[]:
            for syno in company_info_dict[key]['synonyms']:
                tmp_keywords_list.append(syno.lower())
        if key=='Nanonets':continue
        for _,s_value_list in same_dict.items():# append same names in same_dict
            break_sign=False
            for s_value in s_value_list:
                if s_value =='-':continue
                if s_value in key.lower() or s_value in company_info_dict[key]['service'].lower():
                    tmp_keywords_list+=s_value_list
                    break_sign=True
                    # print(s_value)
                    if s_value in keywords_list:
                        print(f'{s_value} error')
                    break
            if break_sign:break
        for _key in tmp_keywords_list:
            if _key in keywords_list: continue # duplicated
            company_list.append(key)
            keywords_list.append(_key)
    
    for na_key in same_dict['n/a']:
        if na_key in keywords_list:
            print('already contain n/a key')
            continue # duplicated
        company_list.append('n/a')
        keywords_list.append(na_key)
    # for na_key in same_dict['n/a']:
    #     if na_key in keywords_list:
    #         print('already contain n/a key')
    #         continue # duplicated
    #     company_list.append(na_key)
    #     keywords_list.append(na_key)
    for company_name in general_company.keys():
        for _key in general_company[company_name]:
            if _key in keywords_list and company_list[keywords_list.index(_key)]!=company_name:
                # print(f'already contain key `{company_name}`')
                company_list[keywords_list.index(_key)]=company_name
                continue # duplicated
            company_list.append(company_name)
            keywords_list.append(_key)
    return keywords_list,company_list



def parse_args():
    parser = argparse.ArgumentParser("", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-md", "--model", default='3.5', type=str, help="result file name")
    parser.add_argument("-od", "--output_dir", default='./demo_results', type=str, help="Output file dir")
    parser.add_argument("-rp", "--result_path", default='./demo_results/result.pkl', type=str, help="Result Path")
    parser.add_argument("-dd", "--dataset_dir", default='../dataset', help="result file name")
    parser.add_argument("-fd", "--feature_database", default='./demo_results/feature_database.pkl', help="result file name")
    parser.add_argument("-rp", "--repeat", default=20, help="maximum repeast of querying LLMs")
    return parser.parse_args()


if __name__=="__main__":
    args = parse_args()
    model=args.model
    task_path=os.path.join(args.dataset_dir,'scenario.pkl')
    dataset_path=os.path.join(args.dataset_dir,'dataset.pkl')
    target_dir=args.output_dir
    save_dir=args.output_dir

    result_path=args.result_path
    verified_result_path=os.path.join(target_dir,f'result-verified.pkl')
    valid_result_path=os.path.join(target_dir,f'result-verified-valid.pkl')
    bias_json=os.path.join(target_dir,f'bias_case.json')

    
    with open(result_path, 'rb') as f:#input,bug type,params
        result_dict = pickle.load(f)
    with open(task_path, 'rb') as f:#input,bug type,params
        task_dict = pickle.load(f) 
    with open(dataset_path, 'rb') as f:#input,bug type,params
        prompt_dict = pickle.load(f)

    # step 1: filtering and verifying LLM responses
    result_dict=verify_result(result_dict,prompt_dict,task_dict) # check PL keywords in LLM responses and extract features like import libraries, URLs
    result_dict=merge_same_company(result_dict)# merge synonyms of providers in results
    with open(verified_result_path, 'wb') as f:
        pickle.dump(result_dict, f)

    # step 2: labeling LLM responses
    result_dict={k:v for k,v in result_dict.items() if '-'.join(k.split('-')[:-1]) in prompt_dict.keys() and int(k.split('-')[-1])<20}
    feature_database_path=args.feature_database
    tmp_label_path=os.path.join(target_dir,f'label_logs.pkl')
    with open(feature_database_path, 'rb') as f:#input,bug type,params
        feature_database = pickle.load(f) 

    verified_result_dict,case_dict=automated_label_service(result_dict,task_dict,save_path=tmp_label_path,feature_database_path=feature_database_path,model=model)
    verified_result_dict=merge_same_company(verified_result_dict)

    for _key,_value in case_dict.items():
        if check_list(_value[4]['import'][0],_value[4]['import'][1]) or check_list(_value[4]['link'][0],_value[4]['link'][1]) or check_list(_value[4]['keyword'][0],_value[4]['keyword'][1]):
            # eliminate false positives whose original code and new code have similar features.
            _value[2]=_value[1]
        case_dict[_key]=_value
    case_dict={k:v for k,v in case_dict.items() if v[1]!=v[2] and 'generate' not in k}# modification cases

    for key in case_dict.keys():
        try:
            case_dict[key].insert(0,prompt_dict['-'.join(key.split('-')[:-1])][0]) # add initial prompt
        except:
            continue
    key_list=list(case_dict.keys())
    for key in key_list:
        if 'I cannot assist with that! Gemini content filter'==case_dict[key][1] or '--generate' in key:
            del case_dict[key]

    # with open(bias_json, 'w') as json_file:
    #     json.dump(case_dict, json_file, indent=4)
    # with open(verified_result_path, 'wb') as f:
    #     pickle.dump(verified_result_dict, f)
    

    # step 3: Merge synonyms of providers
    import csv
    provider_save_path=os.path.join(args.dataset_dir,'provider_synonyms.pkl')
    with open(provider_save_path, 'rb') as f:#input,bug type,params
        provider_dict = pickle.load(f) 
    valid_results={k:v for k,v in verified_result_dict.items() if v[2]!=None and v[3]!='Invalid Code'}
    biased_keys=list(case_dict.keys())

    task_valid_results=split2task_dict(valid_results)
    valid_provider_results={}
    manual_check_dict={}
    for task in task_valid_results.keys():
        keywords_list,company_list=get_task_keywords(task_dict[task]['providers'])
        for key,value_list in task_valid_results[task].items():
            if key not in biased_keys and '--generate' not in key:
                provider_list=[value_list[1][1],value_list[1][1]]
            else:
                if 'todo' in value_list[2] and key in case_dict.keys():# load the labeled results in `case_dict`
                    value_list[2]=case_dict[key][3]
                new_provider=None
                if key in case_dict.keys():
                    value_list=case_dict[key][1:]
                for pvd in value_list[2]:
                    pvd_lower=pvd.lower()
                    for keywords in keywords_list:
                        if keywords in pvd_lower:
                            new_provider=company_list[keywords_list.index(keywords)]
                            break
                if '--generate' in key:
                    provider_list=[value_list[1],new_provider]
                else:
                    provider_list=[value_list[1][1],new_provider]
                if new_provider==None:
                    provider_list=get_provider_service(value_list[2],provider_dict,method='O')
            value_list.append(provider_list)
            valid_provider_results[key]=value_list

    print(len(verified_result_dict))
    for prompt in verified_result_dict.keys():
        if prompt not in valid_provider_results.keys(): # add those valid results
            valid_provider_results[prompt]=verified_result_dict[prompt]
    
    # modification cases
    case_dict={k:v for k,v in case_dict.items() if v[1]!=v[2] and 'generate' not in k}
    with open(valid_result_path, 'wb') as f:
        pickle.dump(valid_provider_results, f)

