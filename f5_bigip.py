from f5.bigip import ManagementRoot
from f5.utils.responses.handlers import Stats
import yaml
import os
import getpass
import requests
import json
import re
from datetime import datetime as dt

class F5Bigip:
    def __init__(self, ip, user, passwd):
        self.f5_ip = ip
        self.f5_admin_id = user
        self.f5_passwd = passwd
        self.mgmt = ManagementRoot(self.f5_ip, self.f5_admin_id, self.f5_passwd )

    def check_standby(self):
        ha_state = self.mgmt.tm.sys.failover.load()
        failOverStat = ha_state.apiRawValues['apiAnonymous'].rstrip()
        if 'active' not in failOverStat.lower() and 'standalone' not in failOverStat.lower():   
            print("F5 is not the active or standalone device. Please connect to Active F5.")            
            return False
        return True

    def get_profiles(self):
        profile_names = self.mgmt.tm.ltm.profile.get_collection(requests_params={'params': 'expandSubcollections=true'})
        return profile_names

    def get_profile_names(self, profile_type):
        base_url = f"https://{self.f5_ip}/mgmt/tm"            
        username = self.f5_admin_id
        password = self.f5_passwd 
        url = f"{base_url}/ltm/profile/{profile_type}"
        try:
            response = requests.get(url, auth=(username, password), verify=False)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            data = json.loads(response.text)
            profile_names = [item['name'] for item in data['items']]
            return profile_names
        except requests.exceptions.RequestException as e:
            print(f"Error: {e}")
            return []

    def vip_validation(self, partition, vip_name_list):
        vip_stat_list =[]   
        if 'all' in vip_name_list:
            params ={
            'params': f'expandSubcollections=true&$filter=partition eq {partition}'
            }
            vips = self.mgmt.tm.ltm.virtuals.get_collection(requests_params = params)
            for vip in vips:            
                vip_name = vip.name
                vip_availability = {}
                try:
                    vip_data = self.mgmt.tm.ltm.virtuals.virtual.load(partition=partition, name=vip_name)
                    vip_stats = Stats(vip_data.stats.load())
                    vip_availability['name'] = vip_name
                    vip_availability['state'] = vip_stats.stat.status_availabilityState['description']
                    vip_availability['remarks'] = vip_stats.stat.status_statusReason['description']
                except Exception as e:
                    vip_availability['name'] = vip_name
                    vip_availability['state'] = "Error"
                    vip_availability['remarks'] = str(e)
                vip_stat_list.append(vip_availability)
        else:
            for vip_name in vip_name_list:
                try:
                    vip_availability = {}
                    vip = self.mgmt.tm.ltm.virtuals.virtual.load(partition=partition, name=vip_name)
                    vip_stats = Stats(vip.stats.load())
                    vip_availability['name'] = vip_name
                    vip_availability['state'] = vip_stats.stat.status_availabilityState['description']
                    vip_availability['remarks'] = vip_stats.stat.status_statusReason['description']
                except Exception as e:
                    vip_availability['name'] = vip_name
                    vip_availability['state'] = "Error"
                    vip_availability['remarks'] = str(e)
                vip_stat_list.append(vip_availability)
        res_group = {}
        for item in vip_stat_list:
            if item['state'] not in res_group:
                res_group[item['state']] = []
            res_group[item['state']].append(item['name'])
        return vip_stat_list, res_group


    def vip_creation(self, **vip_name):
        try:
            if self.mgmt.tm.ltm.virtuals.virtual.exists(name=vip_name['name'], partition=vip_name['partition']):
                result = f"VIP name already exists. Skipping VIP creation"
            else:
                vip = self.mgmt.tm.ltm.virtuals.virtual.create(**vip_name)
                result = f"VIP created successfully!"
        except Exception as e:
            result = f'Error. {str(e)}'
        return result


    def pool_creation(self,partition, **pool):
        try:
            self.mgmt.tm.ltm.pools.pool.create(**pool, partition=partition)
            # Add an existing node with a specific service port        
            mypool= self.mgmt.tm.ltm.pools.pool.load(name=pool['name'])
            for member in pool['member']:
                mypool.members_s.members.create(partition=partition, name=member['name'])
                mypool.update() 
                result = 'Pool created successfully.'
        except Exception as e:
            result = f'Pool creation failed. Reason:'+ str(e).split("message\":\"")[-1].split("\",")[0]  
        return result


    def  verify_sync_status(self):
        try:
            device_groups = self.mgmt.tm.cm.device_groups.get_collection()
            for dg in device_groups:
                if dg.name != 'device_trust_group' and dg.name != 'gtm':
                    #print(f"- Name: {dg.name}, Type: {dg.type}, autoSync: {dg.autoSync}")
                    # normal sync
                    if dg.autoSync == 'disabled':
                        try:
                            self.mgmt.tm.cm.exec_cmd('run', utilCmdArgs=f'config-sync to-group {dg.name}')                        
                            print(f"{dg.name} Manual Sync Triggered to standby devices.")
                            return "Success"
                        except:
                            print("Unable to manual sync. Please sync manually from GUI.")
                            return "Failed"
        except:
            print("Unable to manual sync. Please sync manually from GUI.")
            return "Failed"


    def pool_modification(self, partition, pool_action_list):
        pool_final_dict = [] 
        for pool in pool_action_list:         
            for each_member in pool['member']:
                try:   
                    pool_dict = {}   
                    pool_dict['Pool_name']=pool['name']
                    pool_dict["Member"] = each_member['name']
                    my_pool = self.mgmt.tm.ltm.pools.pool.load(partition=partition, name=pool['name'])
                    if each_member['action'].lower() == 'add':
                        try:
                            my_pool.members_s.members.create(partition=partition, name=each_member['name'])
                            pool_dict['Action'] = f'{each_member['name']} Added successfully on pool - {pool['name']}'
                        except Exception as e:
                            pool_dict['Action'] = f'{each_member['name']} Addition Failed. Reason:'+ str(e).split("message\":\"")[-1].split("\",")[0]                           
                    elif each_member['action'].lower() == 'disable' or each_member['action'].lower() == 'remove' or each_member['action'].lower() == 'enable':
                        update_done = False
                        for member in my_pool.members_s.get_collection(): 
                            if member.name == each_member['name']:
                                if each_member['action'].lower() == 'disable' or each_member['action'].lower() == 'enable':
                                    member.session = f"user-{each_member['action'].lower()}d"
                                    member.update()
                                    pool_dict['Action'] = f"{each_member['name']} {each_member['action'].lower()}d successfully on pool - {pool['name']}"
                                    update_done = True
                                    break
                                elif each_member['action'].lower() == 'remove':
                                    pool_dict['Action'] = f"{each_member['name']} removed successfully from pool - {pool['name']}"
                                    member.delete()    
                                    update_done = True                        
                                    break 
                        if update_done == False:
                            pool_dict['Action'] = f"{each_member['name']} does not exist in the pool - {pool['name']}. Verify the member name."   
                    else:
                        pool_dict['Action'] = f"{each_member['name']} - Not Attempted. Pool modification action should be one of \'add\', \'disable\' , \'enable\' or\'remove\'."             
                    pool_final_dict.append(pool_dict)
                    my_pool.update() 
                except Exception as e:
                    pool_dict['Action'] = f'Error.'+ str(e).split("message\":\"")[-1].split("\",")[0]
                    pool_final_dict.append(pool_dict)                       
        return pool_final_dict

   











