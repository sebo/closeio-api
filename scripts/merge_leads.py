#!/usr/bin/env python
import argparse
from closeio_api import Client as CloseIO_API

parser = argparse.ArgumentParser(description='Detect duplicates & merge leads (see source code for details)')
parser.add_argument('--api-key', '-k', required=True, help='API Key')
parser.add_argument('--development', action='store_true', help='Use a development (testing) server rather than production.')
parser.add_argument('--confirmed', action='store_true', help='Without this flag, no action will be taken (dry run). Use this to perform the merge.')
args = parser.parse_args()

"""
Detect duplicate leads and merge them.

"""


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def green(str):
    print bcolors.OKBLUE + str + bcolors.ENDC

   

def strCleanup(str):
    return str.strip().lower().replace("+","").replace("/","")

desired_status = 'open' # capitalization doesn't matter

api = CloseIO_API(args.api_key, development=args.development)

offset = 0
has_more = True
combinedLeads = {}  

typesToCheck = ["phones","emails"]
combined = {}
combined["emails"] = {} 
combined["phones"] = {}
combined["addresses"] = {}
combined["name"] = {}


statusLabelOrder = {"Kalt":0,"Kontakt":1,"Termin":2,"Kunde":3,"Tot":4,"Investor":5}
"""
get all leads from close io and match them by phone, email and name
"""
num = 0
totalResults = 0
offset = 0
print "loading..."
while has_more:
    leads_merged_this_page = 0
    resp = api.get('lead', data={
        'query': 'sort:display_name',
        '_skip': offset,
        '_fields': 'id,display_name,name,status_label,contacts,opportunities,email_addresses,addresses,phone_numbers,custom'
    })
    leads = resp["data"]
    if "total_results" in resp:
        print str(int(100.0*offset/resp['total_results']))+"%"
    for lead in leads:
        leadId = lead['id']
        num = num +1
        combinedLeads[leadId] = lead
        checkType = "name"
        if lead[checkType]:
            item = strCleanup(lead[checkType])
            if item not in combined[checkType]:
                combined[checkType][item] = []
            if leadId not in combined[checkType][item]:
                combined[checkType][item].append(leadId)
        checkType = "addresses"
        if lead["addresses"]:
            for address in lead["addresses"]:
                items = []
                if ("zipcode" in address) and (address["zipcode"] != "") and ("address_1" in address) and (address["address_1"] != ""):
                    items.append(strCleanup(address["zipcode"])+"."+strCleanup(address["address_1"]))
                if "city" in address and address["city"]!="" and "address_1" in address and address["address_1"] != "":
                    items.append(strCleanup(address["city"])+"."+strCleanup(address["address_1"]))
                for item in items:
                    if item not in combined[checkType]:
                        combined[checkType][item] = []
                    if leadId not in combined[checkType][item]:
                        combined[checkType][item].append(leadId)
        if lead["contacts"]:
            for contact in lead["contacts"]:
                for checkType in typesToCheck:
                    if contact[checkType]:
                        for item in contact[checkType]:
                            item = strCleanup(item[checkType[:-1]])
                            if item not in combined[checkType]:
                                combined[checkType][item] = []
                            if leadId not in combined[checkType][item]:
                                combined[checkType][item].append(leadId)

    offset += max(0, len(leads))
    has_more = resp['has_more']

matchesFound = {}

matchesFound["emails"] = 0
matchesFound["phones"] = 0
matchesFound["name"] = 0
matchesFound["addresses"] = 0

matches = []
for matchType in combined:
    for index in combined[matchType]:
        idlist = combined[matchType][index]
        if len(idlist) > 1:
            matchesFound[matchType] = matchesFound[matchType]+1
            matches.append({"Ids":idlist,"Type":matchType})
print "Emails "+str(matchesFound["emails"])
print "phones "+str(matchesFound["phones"])
print "addresses "+str(matchesFound["addresses"])
print "name "+str(matchesFound["name"])

print ""
print ""
print ""
"""
find highest ranking match and merge
"""

def prettyPrint(str,strType, currentType):
    if strType == currentType:
        green(str)
    else:
        print str

def printLeadRelevantMatchingData(leadId,mtype):
    lead = combinedLeads[leadId]
    print "============================"
    prettyPrint(lead["name"],"name",mtype)
    print lead["id"]
    print lead["status_label"]
    print ""
    if lead["contacts"]:
        for contact in lead["contacts"]:
            if contact["phones"]:
                for phone in contact["phones"]:
                    prettyPrint(phone["phone"],"phones",mtype)
            if contact["emails"]:
                for email in contact["emails"]:
                    prettyPrint(email["email"],"emails",mtype)
    if lead["addresses"]:
        for address in lead["addresses"]:
            prettyPrint(address["zipcode"]+ " " + address["city"],"addresses",mtype)
            prettyPrint(address["address_1"],"addresses",mtype)
    print "============================"
alreadyMergedIds = []
missingStatusLabels = {}
for match in matches:
    highestRankingLeadId = None
    stopMatch = False
    idlist = match["Ids"]
    for leadId in idlist:
        lead = combinedLeads[leadId]
        if highestRankingLeadId == None:
            highestRankingLeadId = leadId
            print leadId
        else:
            if lead["status_label"]:
                if lead["status_label"] not in statusLabelOrder:
                    missingStatusLabels[lead["id"]] = lead["status_label"]
                    stopMatch = True
                    continue
                else:
                    if statusLabelOrder[lead["status_label"]]>statusLabelOrder[combinedLeads[highestRankingLeadId]["status_label"]]:
                        highestRankingLeadId = leadId
    if stopMatch:
        continue
    idlist.remove(highestRankingLeadId)
    for sourceId in idlist:
        if sourceId not in alreadyMergedIds:
            printLeadRelevantMatchingData(sourceId,match["Type"])
            print "======>>"
            printLeadRelevantMatchingData(highestRankingLeadId,match["Type"])
            choice = raw_input("Please type y for merging > ")
            if choice == 'y' :
                print "merged"
                # Merge the leads using the 'Merge Leads' API endpoint
                api.post('lead/merge', data={
                    'source': sourceId,
                    'destination': highestRankingLeadId,
                })
            alreadyMergedIds.append(sourceId)
            print ""
            print ""
            print ""
            print ""
            print ""
            print ""
            print ""
            print ""
            print ""

for index in missingStatusLabels:
    print "please remove/replace the following status labels"
    print "leadId: "+index
    print missingStatusLabels[index]
