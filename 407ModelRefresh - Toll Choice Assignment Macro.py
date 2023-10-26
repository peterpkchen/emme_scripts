# -*- coding: utf-8 -*-
"""
Created on Mon Mar  8 13:58:35 2021

@author: BCRANE
# ~#*********************************************************************
# ~#  NAME    : LOGITAM31_v2016.MAC
# ~#  PURPOSE : Logit AM 2016 Peak Toll Choice Assignment Macro
# ~#*********************************************************************
# ~/ Created by:    iTRANS Consulting- December 2007
# ~/ Modifications: 21 Dec 2007 - Rhys Wolff
# ~/                08 Jan 2008 - Suzette Shiu
# ~/                28 Jan 2008 - Jonathan Chai mod for 407
# ~/                08 Jan 2009 - Jonathan Chai UPDATE
# ~/                22 Jun 2016 - Jason Zhou mod for GTA Model
# ~/                25 Jul 2016 - Jason Zhou Convert to SOLA Assignment
#                   12 Nov 2020 - Balthazar Crane - Converted to Python
"""
import inro.emme.desktop.app as app
import inro.modeller as m
import traceback as _traceback
import inro.emme.matrix as _matrix
import shutil
import os
import pandas as pd
import numpy as np
from copy import deepcopy
import time

def main():
    emp_file = r"C:\Users\pechen\Desktop\407ETR\407 Update\407_Update_EMME\407_Update_Emme.emp"

    desktop = app.start_dedicated(
        visible=True,
        user_initials="PC",
        project = emp_file
    )

    # connect to modeller
    mm = m.Modeller()
    eb = mm.emmebank

    #INRO Tools
    change_matrix = m.Modeller().tool("inro.emme.data.matrix.change_matrix_properties")
    create_matrix =  m.Modeller().tool("inro.emme.data.matrix.create_matrix")
    copy_matrix = m.Modeller().tool("inro.emme.data.matrix.copy_matrix")
    matrix_calculator = m.Modeller().tool("inro.emme.matrix_calculation.matrix_calculator")
    matrix_balance = m.Modeller().tool("inro.emme.matrix_calculation.matrix_balancing")
    traffic_assignment = m.Modeller().tool("inro.emme.traffic_assignment.sola_traffic_assignment")
    transpose_matrix = m.Modeller().tool("inro.emme.data.matrix.transpose_matrix")
    create_extra = m.Modeller().tool("inro.emme.data.extra_attribute.create_extra_attribute")
    network_calculator= m.Modeller().tool("inro.emme.network_calculation.network_calculator")

    #TMG Tools
    import_matrices = mm.tool("tmg.input_output.import_binary_matrix")  

    #407 Toolbox
    apply_Tolls = m.Modeller().tool("hdr407.apply_road_tolls")

    #Various needed functions and specs

    netCalcSpec = {
        "result": None,
        "expression": None,
        "aggregation": None,
        "selections": {
            "link": "all"
        },
        "type": "NETWORK_CALCULATION"
    }

    def link_calculation(result,exp,selection,scen):
        calc = deepcopy(netCalcSpec)
        calc["result"] = result
        calc["expression"] = exp
        calc["selections"]["link"] = selection
        return network_calculator(calc, scenario = scen)

    mcSpec = {
        "expression": None,
        "result": "",
        "constraint": {
            "by_value": None,
            "by_zone": None
        },
        "aggregation": {
            "origins": None,
            "destinations": None
        },
        "type": "MATRIX_CALCULATION"
    }

    mcConstraint = {
                "interval_min": 0,
                "interval_max": 0,
                "condition": "EXCLUDE",
                "od_values": None
            }


    def matrix_calculation(result,exp,scen):
        mat_calc = deepcopy(mcSpec)
        mat_calc["expression"] = exp
        mat_calc["result"] = result
        matrix_calculator(mat_calc, scenario = scen)
        
    def matrix_calculation_constrained(result,exp,scen,constraint_mat,condition):
        mat_calc = deepcopy(mcSpec)
        mat_calc["expression"] = exp
        mat_calc["result"] = result
        constraint = deepcopy(mcConstraint)
        constraint["od_values"] = constraint_mat
        constraint["condition"] = condition
        mat_calc["constraint"]["by_value"] = constraint
        matrix_calculator(mat_calc, scenario = scen)


    solaSpec = {
        "type": "SOLA_TRAFFIC_ASSIGNMENT",
        "classes": [
            {
                "mode": None, # Need to fill in mode
                "demand": None, #need demand
                "generalized_cost": {
                    "link_costs": None, # Should be specific to mode being assigned
                    "perception_factor": 1
                },
                "results": {
                    "link_volumes": None,
                    "turn_volumes": None,
                    "od_travel_times": {
                        "shortest_paths": None #Should be specific to mode
                    }
                },
                "path_analyses": []
            }
        ],
        "performance_settings": {
            "number_of_processors": "max-1"
        },
        "background_traffic": None,
        "stopping_criteria": {
            "max_iterations": 0,
            "relative_gap": 0.0001,
            "best_relative_gap": 0.01,
            "normalized_gap": 0.005
        }
    }
    select_link = [
                    {
                        "link_component": "@tolls",
                        "turn_component":None,
                        "operator": "+",
                        "selection_threshold": {
                            "lower": None,
                            "upper": None
                        },
                        "path_to_od_composition": {
                            "considered_paths": "ALL",
                            "multiply_path_proportions_by": {
                                "analyzed_demand": False,
                                "path_value": True
                            }
                        },
                        "analyzed_demand": None,
                        "results": {
                            "selected_link_volumes":None,
                            "selected_turn_volumes": None,
                            "od_values": None # Should be specific to assignment
                        }
                    }
                ]

    sel_dict = {
                        "link_component": "@tolls",
                        "turn_component":None,
                        "operator": "+",
                        "selection_threshold": {
                            "lower": None,
                            "upper": None
                        },
                        "path_to_od_composition": {
                            "considered_paths": "ALL",
                            "multiply_path_proportions_by": {
                                "analyzed_demand": False,
                                "path_value": True
                            }
                        },
                        "analyzed_demand": None,
                        "results": {
                            "selected_link_volumes":None,
                            "selected_turn_volumes": None,
                            "od_values": None # Should be specific to assignment
                        }
                    }

    def assign_and_extract_cost(mode,demand,cost,gen_cost,extract_toll,scen,link_toll=None, toll_att = None):
        assn_1 = deepcopy(solaSpec)
        assn_1["classes"][0]["mode"] = mode
        assn_1["classes"][0]["demand"] = demand
        assn_1["classes"][0]["generalized_cost"]["link_costs"] = cost
        assn_1["classes"][0]["results"]["od_travel_times"]["shortest_paths"] = gen_cost
        if extract_toll == True:
            sel_assn1 = deepcopy(select_link)
            sel_assn1[0]["link_component"] = toll_att
            sel_assn1[0]["results"]["od_values"] = link_toll
            assn_1["classes"][0]["path_analyses"] = sel_assn1
        traffic_assignment(assn_1, scenario = scen)
        
    def just_assign(mode,demand,cost,scen):
        assn_1 = deepcopy(solaSpec)
        assn_1["classes"][0]["mode"] = mode
        assn_1["classes"][0]["demand"] = demand
        assn_1["classes"][0]["generalized_cost"]["link_costs"] = cost
        traffic_assignment(assn_1, scenario = scen)
        
    def final_assignment(mode,demand,cost,scen,toll_flag,cost_att,link_cost,ivtt_att,link_ivtt,toll_att=None,link_toll=None):
        assn_1 = deepcopy(solaSpec)
        assn_1["classes"][0]["mode"] = mode
        assn_1["classes"][0]["demand"] = demand
        assn_1["classes"][0]["generalized_cost"]["link_costs"] = cost
        
        sel_assn1 = []
        sel_1 = deepcopy(sel_dict)
        sel_2 = deepcopy(sel_dict)
        
        sel_1["link_component"] = cost_att
        sel_1["results"]["od_values"] = link_cost
        
        sel_2["link_component"] = ivtt_att
        sel_2["results"]["od_values"] = link_ivtt
        
        sel_assn1.append(sel_1)
        sel_assn1.append(sel_2)
        
        if toll_flag:
            sel_3 = deepcopy(sel_dict)
            sel_3["link_component"] = toll_att
            sel_3["results"]["od_values"] = link_toll
            sel_assn1.append(sel_3)
        
        assn_1["classes"][0]["path_analyses"] = sel_assn1
        print(assn_1)
        traffic_assignment(assn_1, scenario = scen)
        
    def calculate_traveltime(scen):
        link_calculation("@ttime","(length*60/ul2)*((1+put((@itvol+volad)/(lanes*ul3))^6)*(get(1).le.1)+(6*get(1)-4)*(get(1).gt.1))","vdf=11 or vdf=14",scen)
        link_calculation("@ttime","(length*60/ul2)*((1+put((@itvol+volad)/(lanes*ul3))^4)*(get(1).le.1)+(4*get(1)-2)*(get(1).gt.1))","vdf=13 or vdf=15,51", scen)
        link_calculation("@ttime","(length*60/ul2)","vdf=90",scen)
        
    class TCAM(m.Tool()):
        Scenario = m.Attribute(int)
        tollAtt_auto = m.Attribute(str)
        tollAtt_light = m.Attribute(str)
        tollAtt_heavy = m.Attribute(str)
        tollFlag = m.Attribute(str)
        rampFlag = m.Attribute(str)
        iterations = m.Attribute(int)
        artVOC = m.Attribute(float)
        freewayVOC = m.Attribute(float)
        baseVOT = m.Attribute(float)
        rampPen = m.Attribute(float)
        pdi = m.Attribute(float)
        lmbda = m.Attribute(float)
        etcDis = m.Attribute(float)
        ltVOT = m.Attribute(float)
        mtVOT = m.Attribute(float)
        htVOT = m.Attribute(float)
        
        def __init__(self):
            self.Scenario = mm.scenario
            
        def page(self):
            pb = m.ToolPageBuilder(self)
            pb.title = "Run the TCAM algorithm"
            return pb.render()
        
        def run(self):
            pass
        
        def __call__(self,Scenario, tollAtt_auto, tollAtt_light,tollAtt_heavy,tollFlag,rampFlag,
                    iterations, artVOC, freewayVOC, baseVOT, rampPen, pdi, lmbda, etcDis,ltVOT,
                    mtVOT,htVOT):
            
            scen = eb.scenario(Scenario)
            
            #Pre-Run Set Up
            initial_atts = {"@ttime":"travel time",
                        "@acvol":"actual volume",
                        "@itvol":"iteration volume",
                        "@cong":"congestion factor",
                        "@atvol":"auto toll vol",
                            "@anvol":"auto non-toll vol",
                            "@ltvol":"light truck toll vol",
                            "@lnvol":"light truck non-toll vol",
                            "@mtvol":"medium truck toll vol",
                            "@mnvol":"medium truck non-toll vol",
                            "@htvol":"heavy truck toll vol",
                            "@hnvol":"heavy truck non-toll vol",
                            "@catvol":"cumul auto toll vol",
                            "@canvol":"cumul auto non-toll vol",
                            "@cltvol":"cumul light truck toll vol",
                            "@clnvol":"cumul light truck non-toll vol",
                            "@cmtvol":"cumul medium truck toll vol",
                            "@cmnvol":"cumul medium truck non-toll vol",
                            "@chtvol":"cumul heavy truck toll vol",
                            "@chnvol":"cumul heavy truck non-toll vol",
                        "@cuacv":"cumulative actual vol",
                        "@tolls":"year adjusted toll",
                        "@atgc":"gen cost eq for auto toll usrs",
                        "@ltgc":"gen cost eq for light trk toll usrs",
                        "@mtgc":"gen cost eq for med trk toll usrs",
                        "@htgc":"gen cost eq for heavy trk toll usrs",
                        "@angc":"gen cost eq for auto non-toll usrs",
                        "@lngc":"gen cost eq for light trk non-toll usrs",
                        "@mngc":"gen cost eq for med trk non-toll usrs",
                        "@hngc":"gen cost eq for heavy trk non-toll usrs",
                        "@avoc": "auto operating cost"}
            
            for att in initial_atts:
                create_extra(extra_attribute_type="LINK",
                            extra_attribute_name=att,
                            extra_attribute_description=initial_atts[att],
                            overwrite=True,
                            scenario = scen)
            
            link_calculation("@ttime","length*60/ul2","all",scen)
            
            auto_dem = "mf10"
            lt_dem = "mf11"
            mt_dem = "mf12"
            ht_dem = "mf13"

            auto_t_tolls_mat = "mf100"
            lt_t_tolls_mat = "mf101"
            mt_t_tolls_mat = "mf102"
            ht_t_tolls_mat = "mf103"
            
            auto_t_gc_mat = "mf104"
            lt_t_gc_mat = "mf105"
            mt_t_gc_mat = "mf106"
            ht_t_gc_mat = "mf107"
            
            auto_nt_gc_mat = "mf108"
            lt_nt_gc_mat = "mf109"
            mt_nt_gc_mat = "mf110"
            ht_nt_gc_mat = "mf111"
            
            auto_t_dem_mat = "mf112"
            lt_t_dem_mat = "mf113"
            mt_t_dem_mat = "mf114"
            ht_t_dem_mat = "mf115"
            
            auto_nt_dem_mat = "mf116"
            lt_nt_dem_mat = "mf117"
            mt_nt_dem_mat = "mf118"
            ht_nt_dem_mat = "mf119"
            
            auto_t_toll_final = "mf120"
            auto_t_cost_final = "mf121"
            auto_nt_cost_final = "mf122"
            auto_t_ivtt_final = "mf123"
            auto_nt_ivtt_final = "mf124"
            
            auto_cost_weighted = "mf125"
            auto_ivtt_weighted = "mf126"
            
            mats = {auto_t_tolls_mat:["auto_t_tolls_mat","Auto Toll paid"],
            lt_t_tolls_mat:["lt_t_tolls_mat","Light Truck Toll paid"],
            mt_t_tolls_mat:["mt_t_tolls_mat","Medium Truck Toll paid"],
            ht_t_tolls_mat:["ht_t_tolls_mat","Heavy Truck Toll paid"],
            auto_t_gc_mat:["auto_t_gc_mat","Auto Generalized Cost (Toll Users)"],
            lt_t_gc_mat:["lt_t_gc_mat","Light Truck Generalized Cost (Toll Users)"],
            mt_t_gc_mat:["mt_t_gc_mat","Medium Truck Generalized Cost (Toll Users)"],
            ht_t_gc_mat:["ht_t_gc_mat","Heavy Truck Generalized Cost (Toll Users)"],
            auto_nt_gc_mat:["auto_nt_gc_mat","Auto Generalized Cost (Non-Toll Users)"],
            lt_nt_gc_mat:["lt_nt_gc_mat","Light Truck Generalized Cost (Non-Toll Users)"],
            mt_nt_gc_mat:["mt_nt_gc_mat","Medium Truck Generalized Cost (Non-Toll Users)"],
            ht_nt_gc_mat:["ht_nt_gc_mat","Heavy Truck Generalized Cost (Non-Toll Users)"],
            auto_t_dem_mat:["auto_t_dem_mat","Auto Toll TCAM Demand"],
            lt_t_dem_mat:["lt_t_dem_mat","Light Truck TCAM Demand"],
            mt_t_dem_mat:["mt_t_dem_mat","Medium Truck TCAM Demand"],
            ht_t_dem_mat:["ht_t_dem_mat","Heavy Truck TCAM Demand"],
            auto_nt_dem_mat:["auto_nt_dem_mat","Auto TCAM Demand"],
            lt_nt_dem_mat:["lt_nt_dem_mat","Light Truck TCAM Demand"],
            mt_nt_dem_mat:["mt_nt_dem_mat","Medium Truck TCAM Demand"],
            ht_nt_dem_mat:["ht_nt_dem_mat","Heavy Truck TCAM Demand"],
            auto_t_toll_final:["auto_t_toll_final","Toll mat last iteration"],
            auto_t_cost_final:["auto_t_cost_final","Auto toll cost last iteration"],
            auto_nt_cost_final:["auto_nt_cost_final","Auto NonToll cost last iteration"],
            auto_t_ivtt_final:["auto_t_ivtt_final","Auto toll ivtt last iteration"],
            auto_nt_ivtt_final:["auto_nt_ivtt_final","Auto non-toll ivtt last iteration"],  
            auto_cost_weighted:["auto_cost_weighted","Auto cost weighted last iteration"],
            auto_ivtt_weighted:["auto_ivtt_weighted","Auto ivtt weighted last iteration"]}
            
            for mat in mats:
                create_matrix(matrix_id = mat,
                            matrix_name = mats[mat][0],
                            matrix_description = mats[mat][1],
                            overwrite = True,
                            scenario = scen)
                
            # apply_Tolls(TollFile, RampFile, Scenario, tollAtt_auto, tollAtt_light,tollAtt_heavy,tollFlag,rampFlag,vidsurcharge,flatToll)
            exp1 = "{}*length".format(artVOC)
            exp2 = "*(vdf!=11&&vdf!=12&&vdf!=13&&vdf!=14&&vdf!=91&&vdf!=92&&vdf!=96&&vdf!=97)"
            exp3 = "+{}*length".format(freewayVOC)
            exp4 = "*(vdf==11||vdf==12||vdf==13||vdf==14||vdf==91||vdf==92||vdf==96||vdf==97)"
            exp = exp1 + exp2 + exp3 + exp4
            link_calculation("@avoc",exp,"all",scen)
            #Now... begin the TCAM
            print("Release the TCAM")
            for i in range(iterations):
                t = time.localtime()
                current_time = time.strftime("%H:%M:%S", t)
                #print("Now commencing iteration {0} at time {1}".format(i+1,current_time))
                link_calculation("@cong","((@ttime*ul2/length/60).max.1).min.1.55","all",scen)
                
                exp1 = "(@ttime*@cong+{0}*({1}!=0)+{2}*length".format(rampPen,rampFlag,artVOC)
                exp2 = "*(vdf!=11&&vdf!=12&&vdf!=13&&vdf!=14&&vdf!=91&&vdf!=92&&vdf!=96&&vdf!=97)/{0}/{1}*60".format(baseVOT,pdi)
                exp3 = "+{}*length".format(freewayVOC)
                exp4 = "*(vdf==11||vdf==12||vdf==13||vdf==14||vdf==91||vdf==92||vdf==96||vdf==97)/{0}/{1}*60).min.9999".format(baseVOT,pdi)
                exp = exp1 + exp2 + exp3 + exp4
                link_calculation("@atgc",exp,"all",scen)
                
                exp1 = "(@ttime*@cong+{0}*({1}!=0)+{2}*length".format(rampPen,rampFlag,artVOC)
                exp2 = "*(vdf!=11&&vdf!=12&&vdf!=13&&vdf!=14&&vdf!=91&&vdf!=92&&vdf!=96&&vdf!=97)/{0}/{1}*60".format(ltVOT,pdi)
                exp3 = "+{}*length".format(freewayVOC)
                exp4 = "*(vdf==11||vdf==12||vdf==13||vdf==14||vdf==91||vdf==92||vdf==96||vdf==97)/{0}/{1}*60).min.9999".format(ltVOT,pdi)
                exp = exp1 + exp2 + exp3 + exp4
                link_calculation("@ltgc",exp,"all",scen)
                
                exp1 = "(@ttime*@cong+{0}*({1}!=0)+{2}*length".format(rampPen,rampFlag,artVOC)
                exp2 = "*(vdf!=11&&vdf!=12&&vdf!=13&&vdf!=14&&vdf!=91&&vdf!=92&&vdf!=96&&vdf!=97)/{0}/{1}*60".format(mtVOT,pdi)
                exp3 = "+{}*length".format(freewayVOC)
                exp4 = "*(vdf==11||vdf==12||vdf==13||vdf==14||vdf==91||vdf==92||vdf==96||vdf==97)/{0}/{1}*60).min.9999".format(mtVOT,pdi)
                exp = exp1 + exp2 + exp3 + exp4
                link_calculation("@mtgc",exp,"all",scen)
                
                exp1 = "(@ttime*@cong+{0}*({1}!=0)+{2}*length".format(rampPen,rampFlag,artVOC)
                exp2 = "*(vdf!=11&&vdf!=12&&vdf!=13&&vdf!=14&&vdf!=91&&vdf!=92&&vdf!=96&&vdf!=97)/{0}/{1}*60".format(htVOT,pdi)
                exp3 = "+{}*length".format(freewayVOC)
                exp4 = "*(vdf==11||vdf==12||vdf==13||vdf==14||vdf==91||vdf==92||vdf==96||vdf==97)/{0}/{1}*60).min.9999".format(htVOT,pdi)
                exp = exp1 + exp2 + exp3 + exp4
                link_calculation("@htgc",exp,"all",scen)
                
                # print("Now beginning initial Assignment of Auto mode")
                assign_and_extract_cost("c",auto_dem,"@atgc",auto_t_gc_mat,True,scen,auto_t_tolls_mat,tollAtt_auto)
                # print("Now beginning initial Assignment of Light truck mode")
                assign_and_extract_cost("d",lt_dem,"@ltgc",lt_t_gc_mat,True,scen,lt_t_tolls_mat,tollAtt_auto)
                # print("Now beginning initial Assignment of Medium truck mode")
                assign_and_extract_cost("e",mt_dem,"@mtgc",mt_t_gc_mat,True,scen,mt_t_tolls_mat,tollAtt_light)
                # print("Now beginning initial Assignment of Heavy truck mode")
                assign_and_extract_cost("f",ht_dem,"@htgc",ht_t_gc_mat,True,scen,ht_t_tolls_mat,tollAtt_heavy)
                
                matrix_calculation(auto_t_tolls_mat, "{}/{}/{}*60".format(auto_t_tolls_mat,baseVOT,pdi),scen)
                matrix_calculation(lt_t_tolls_mat, "{}/{}/{}*60".format(lt_t_tolls_mat,ltVOT,pdi),scen)
                matrix_calculation(mt_t_tolls_mat, "{}/{}/{}*60".format(mt_t_tolls_mat,mtVOT,pdi),scen)
                matrix_calculation(ht_t_tolls_mat, "{}/{}/{}*60".format(ht_t_tolls_mat,htVOT,pdi),scen)
                
                link_calculation("@angc","9999","!@highw=0",scen)
                link_calculation("@angc","@atgc","@highw=0",scen)
                link_calculation("@lngc","9999","!@highw=0",scen)
                link_calculation("@lngc","@ltgc","@highw=0",scen)
                link_calculation("@mngc","9999","!@highw=0",scen)
                link_calculation("@mngc","@mtgc","@highw=0",scen)
                link_calculation("@hngc","9999","!@highw=0",scen)
                link_calculation("@hngc","@htgc","@highw=0",scen)
                
                # print("Now beginning initial Assignment of Auto mode without 407")
                assign_and_extract_cost("c",auto_dem,"@angc",auto_nt_gc_mat,False,scen)
                # print("Now beginning initial Assignment of Light truck mode without 407")
                assign_and_extract_cost("d",lt_dem,"@lngc",lt_nt_gc_mat,False,scen)
                # print("Now beginning initial Assignment of Medium truck mode without 407")
                assign_and_extract_cost("e",mt_dem,"@mngc",mt_nt_gc_mat,False,scen)
                # print("Now beginning initial Assignment of Heavy Truck mode without 407")
                assign_and_extract_cost("f",ht_dem,"@hngc",ht_nt_gc_mat,False,scen)
                
                #Calculate Utilities by class for toll choice
                # print("Computing Utilities")
                exp = "{0}/(1+exp({1}*({2}+{3}*{4}-{5})))".format(auto_dem,lmbda,auto_t_gc_mat,etcDis,auto_t_tolls_mat,auto_nt_gc_mat)
                matrix_calculation(auto_t_dem_mat,exp,scen)
                matrix_calculation(auto_nt_dem_mat,auto_dem + " - " + auto_t_dem_mat,scen)
                
                exp = "{0}/(1+exp({1}*({2}+{3}*{4}-{5})))".format(lt_dem,lmbda,lt_t_gc_mat,etcDis,lt_t_tolls_mat,lt_nt_gc_mat)
                matrix_calculation(lt_t_dem_mat,exp,scen)
                matrix_calculation(lt_nt_dem_mat,lt_dem + " - " + lt_t_dem_mat,scen)
                
                exp = "{0}/(1+exp({1}*({2}+{3}*{4}-{5})))".format(mt_dem,lmbda,mt_t_gc_mat,etcDis,mt_t_tolls_mat,mt_nt_gc_mat)
                matrix_calculation(mt_t_dem_mat,exp,scen)
                matrix_calculation(mt_nt_dem_mat,mt_dem + " - " + mt_t_dem_mat,scen)
                
                exp = "{0}/(1+exp({1}*({2}+{3}*{4}-{5})))".format(ht_dem,lmbda,ht_t_gc_mat,etcDis,ht_t_tolls_mat,ht_nt_gc_mat)
                matrix_calculation(ht_t_dem_mat,exp,scen)
                matrix_calculation(ht_nt_dem_mat,ht_dem +" - " + ht_t_dem_mat,scen)
                
                #Assign all modes based on recalculated demand
                # print("Now beginning auto toll user assignment")
                
                if i == (iterations-1): #Final iteration
                    
                    final_assignment("c",auto_t_dem_mat,"@atgc",scen,True,"@avoc",auto_t_cost_final,"@ttime",auto_t_ivtt_final,tollAtt_auto,auto_t_toll_final)
                    link_calculation("@acvol","volau","all",scen)
                    link_calculation("@atvol","volau","all",scen)
                    link_calculation("@catvol","@catvol + volau","all",scen)
                    
                    final_assignment("c",auto_nt_dem_mat,"@angc",scen,False,"@avoc",auto_nt_cost_final,"@ttime",auto_nt_ivtt_final)
                    link_calculation("@acvol","@acvol+volau","all",scen)
                    link_calculation("@anvol","volau","all",scen)
                    link_calculation("@canvol","@canvol + volau","all",scen)
                    
                    exp_cost_num = "(" + auto_t_dem_mat + "*" + auto_t_cost_final + "+" + auto_nt_dem_mat + "*" + auto_nt_cost_final + ")"
                    exp_cost_den = auto_dem
                    
                    matrix_calculation_constrained(auto_cost_weighted,exp_cost_num + "/" + exp_cost_den,scen,auto_dem,"EXCLUDE")
                    matrix_calculation_constrained(auto_cost_weighted,auto_nt_cost_final,scen,auto_cost_weighted,"INCLUDE")
                    
                    exp_ivtt_num = "(" + auto_t_dem_mat + "*" + auto_t_ivtt_final + "+" + auto_nt_dem_mat + "*" + auto_nt_ivtt_final + ")"
                    exp_ivtt_den = auto_dem
                    
                    matrix_calculation_constrained(auto_ivtt_weighted,exp_ivtt_num + "/" + exp_ivtt_den,scen,auto_dem,"EXCLUDE")
                    matrix_calculation_constrained(auto_ivtt_weighted,auto_nt_ivtt_final,scen,auto_ivtt_weighted,"INCLUDE")
                else:
                    just_assign("c",auto_t_dem_mat,"@atgc",scen)
                    link_calculation("@acvol","volau","all",scen)
                    link_calculation("@atvol","volau","all",scen)
                    link_calculation("@catvol","@catvol + volau","all",scen)
                    
                    just_assign("c",auto_nt_dem_mat,"@angc",scen)
                    link_calculation("@acvol","@acvol+volau","all",scen)
                    link_calculation("@anvol","volau","all",scen)
                    link_calculation("@canvol","@canvol + volau","all",scen)
                
                assn_modes = [["d",lt_t_dem_mat,"@ltgc","@ltvol","@cltvol"],
                            ["d",lt_nt_dem_mat,"@lngc","@lnvol","@clnvol"],
                            ["e",mt_t_dem_mat,"@mtgc","@mtvol","@cmtvol"],
                            ["e",mt_nt_dem_mat,"@mngc","@mnvol","@cmnvol"],
                            ["f",ht_t_dem_mat,"@htgc","@htvol","@chtvol"],
                            ["f",ht_nt_dem_mat,"@hngc","@hnvol","@chnvol"]]
                
                for modes in assn_modes:
                    # print("Now beginning assignment of mode {0}, demand {1}".format(modes[0],modes[1]))
                    just_assign(modes[0],modes[1],modes[2],scen)
                    link_calculation("@acvol","@acvol+volau","all",scen)
                    link_calculation(modes[3],"volau","all",scen)
                    link_calculation(modes[4],modes[4] + "+volau","all",scen)
                    
                link_calculation("@itvol", "(@itvol/{0}*{1})+(@acvol/{0})".format(i+1,i),"all",scen)
                link_calculation("@cuacv", "@cuacv + @acvol","all",scen)
                # print("Re-computing travel times")
                calculate_traveltime(scen)
            link_calculation("@cuacv","@cuacv/" + str(iterations),"all",scen)
            link_calculation("@catvol","@catvol/" + str(iterations),"all",scen)
            link_calculation("@canvol","@canvol/" + str(iterations),"all",scen)
            link_calculation("@cltvol","@cltvol/" + str(iterations),"all",scen)
            link_calculation("@clnvol","@clnvol/" + str(iterations),"all",scen)
            link_calculation("@cmtvol","@cmtvol/" + str(iterations),"all",scen)
            link_calculation("@cmnvol","@cmnvol/" + str(iterations),"all",scen)
            link_calculation("@chtvol","@chtvol/" + str(iterations),"all",scen)
            link_calculation("@chnvol","@chnvol/" + str(iterations),"all",scen)
            print("TCAM complete!")
            
