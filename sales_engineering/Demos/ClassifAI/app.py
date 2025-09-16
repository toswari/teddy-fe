import time
import streamlit as st
from streamlit_lottie import st_lottie_spinner
import requests

import os
import traceback
import json
from pathlib import Path
from getpass import getpass
from google.protobuf.struct_pb2 import Struct

from clarifai.client.model import Model, Inputs
from clarifai.client.search import Search
from clarifai.client.input import Inputs
from clarifai_grpc.channel.clarifai_channel import ClarifaiChannel
from clarifai_grpc.grpc.api import service_pb2_grpc, service_pb2, resources_pb2
from tenacity import retry, stop_after_attempt, wait_exponential

# Set up Clarifai credentials
CLARIFAI_PAT = st.secrets["CLARIFAI_PAT"]  # Store in Streamlit secrets
USER_ID = st.secrets["CLARIFAI_USER_ID"]  # Store in Streamlit secrets

MODEL_URL = "https://clarifai.com/meta/Llama-3/models/Llama-3_2-3B-Instruct"
#MODEL_URL= "https://clarifai.com/meta/Llama-4/models/Llama-4-Scout-17B-16E-Instruct"

lottie_url = "https://assets9.lottiefiles.com/packages/lf20_j1adxtyb.json"
lottie_json = requests.get(lottie_url).json()

ODI_PROMPT = """
Below is the ODNI Classification Guide:

===== Begin ODNI Classification Guide =====

Item: The fact that NCTC uses FlSA-acquired and FISA- derived information in its analysis and in its intelligence products.
Classification Level: U
Remarks: UNCLASSIFIED when used generically.
Classification Guide: ODNI Classification Guide - 3.3.1 Foreign Intelligence Surveillance Act (FISA)

----

Item: Information obtained by, or derived from, an investigateive technique requiring a FISA Court order or other FISA authorized collection. (" FISA Information").
Classification Level: S
Derivative: ODNI FISA S-14
Dissem Control: NOFORN//FISA
Reason: 1.4(c)
Declass On: Current date + 25 years
OCA: FBI
Remarks: May be classified higher based on individual collection agency or assisting agency classification guidance.
Classification Guide: ODNI Classification Guide - 3.3.1 Foreign Intelligence Surveillance Act (FISA)

----

Item: Use of FISA-acquired and FISA-derived information when connected to a particular target or ana1Y1ic judgment in intelligence products or analysis.
Classification Level: S
Derivative: ODNI FISA S-14
Dissem Control: NOFORN//FISA
Reason: 1.4(c)
Declass On: Current date + 25 years
Remarks: May be classified higher based on individual collection agency classification guidance.
Classification Guide: ODNI Classification Guide - 3.3.1 Foreign Intelligence Surveillance Act (FISA)

----

Item: The fact ofNCTC's access to and use of raw, unminimized FISA-acquired information.
Classification Level: S
Derivative: ODNI FISA S-14
Dissem Control: NOFORN
Reason: 1.4(c)
Declass On: Current date + 25 years
Classification Guide: ODNI Classification Guide - 3.3.1 Foreign Intelligence Surveillance Act (FISA)

----

Item: The process and procedures of making raw, unminimized FISA-acquired information available to NCTC personnel.
Classification Level: S
Derivative: ODNI FISA S-14
Dissem Control: NOFORN
Reason: 1.4(c)
Declass On: Current date + 25 years
Classification Guide: ODNI Classification Guide - 3.3.1 Foreign Intelligence Surveillance Act (FISA)

----

Item: NCTC's Standard Minimization Procedures.
Classification Level: S
Derivative: ODNI FISA S-14
Dissem Control: NOFORN
Reason: 1.4(c)
Declass On: Current date + 25 years
Classification Guide: ODNI Classification Guide - 3.3.1 Foreign Intelligence Surveillance Act (FISA)

----

Item: The policies, process, and procedures for implementing NCTC's Standard Minimization Procedures.
Classification Level: S
Derivative: ODNI FISA S-14
Dissem Control: NOFORN
Reason: 1.4(c)
Declass On: Current date + 25 years
OCA: AG
Classification Guide: ODNI Classification Guide - 3.3.1 Foreign Intelligence Surveillance Act (FISA)

----

Item: The fact that NCTC employees are required to sign a Leuer ofConsent to View and Work with Objectionable Material in order to access unminimized FISA ac uired information.
Classification Level: S
Derivative: ODNI FISA S-14
Dissem Control: NOFORN
Reason: 1.4(c)
Declass On: Current date + 25 years
Classification Guide: ODNI Classification Guide - 3.3.1 Foreign Intelligence Surveillance Act (FISA)

----

Item: The fact ofthe existence ofthe FISA Source Registry.
Classification Level: U
Dissem Control: FOUO
Classification Guide: ODNI Classification Guide - 3.3.1 Foreign Intelligence Surveillance Act (FISA)

----

Item: The fact that all products that contain FISA- derived information must include the NCTC FISA caveat.
Classification Level: U
Dissem Control: FOUO
Classification Guide: ODNI Classification Guide - 3.3.1 Foreign Intelligence Surveillance Act (FISA)

----

Item: The NCTC FISA caveat.
Classification Level: U
Classification Guide: ODNI Classification Guide - 3.3.1 Foreign Intelligence Surveillance Act (FISA)

----

Item: Budget or finance information to support the NCTC FISA program.
Classification Level: S
Derivative: ODNI FISA S-14
Dissem Control: NOFORN
Reason: 1.4(c)
Declass On: Current date + 25 years
Classification Guide: ODNI Classification Guide - 3.3.1 Foreign Intelligence Surveillance Act (FISA)

----

Item: he fact that NCTC has a FISA Coordinator (FC) who serves as the focal point for managing the implementation ofNCTC's FISA authorities and responsibilities.
Classification Level: U
Classification Guide: ODNI Classification Guide - 3.3.1 Foreign Intelligence Surveillance Act (FISA)

----

Item: The general description of the FISA Coordinator's responsibilities.
Classification Level: U
Remarks: May be classified higher when the information includes a reference to NCTC's raw, unminimized FISA authorities and processes.
Classification Guide: ODNI Classification Guide - 3.3.1 Foreign Intelligence Surveillance Act (FISA)

----

Item: The fact that NCTC has individuals who function as FISA Analysts or FISA Advanced Analysts.
Classification Level: U
Remarks: May be classified higher when associated with a description of the FISA Analyst role and corresponding data accesses.
Classification Guide: ODNI Classification Guide - 3.3.1 Foreign Intelligence Surveillance Act (FISA)

----

Item: The fact that NCTC has individuals who function as FISA Minimization Approvers.
Classification Level: S
Derivative: ODNI FISA S-14
Dissem Control: NOFORN
Reason: 1.4(c)
Declass On: Current date + 25 years
Classification Guide: ODNI Classification Guide - 3.3.1 Foreign Intelligence Surveillance Act (FISA)

----

Item: The fact that NCTC has individuals who function as FISA Dissemination Nominators.
Classification Level: U
Remarks: May be classified higher when associated with a description ofthe FISA Dissemination Nominator role and corresponding data accesses.
Classification Guide: ODNI Classification Guide - 3.3.1 Foreign Intelligence Surveillance Act (FISA)

----

Item: he fact that NCTC has individuals who function as FISA Dissemination Approvers.
Classification Level: U
Remarks: May be classified higher when associated with a description o f the FISA Dissemination Approver role and corresponding data accesses.
Classification Guide: ODNI Classification Guide - 3.3.1 Foreign Intelligence Surveillance Act (FISA)

----

Item: The fact that NCTC has individuals who function as FISA Notification Points ofContact (POCs)
Classification Level: U
Remarks: May be classified higher when associated with a description o f the FISA Notification POC role and corresponding data accesses.
Classification Guide: ODNI Classification Guide - 3.3.1 Foreign Intelligence Surveillance Act (FISA)

----

Item: The fact that NCTC has individuals who function as FISA Auditors.
Classification Level: U
Remarks: May be classified higher when associated with a description of the FISA Auditor role and corresponding data accesses.
Classification Guide: ODNI Classification Guide - 3.3.1 Foreign Intelligence Surveillance Act (FISA)

----

Item: The fact that NCTC has individuals who function as FISA Systems Administrators.
Classification Level: U
Remarks: May be classified higher when associated with a description ofthe FISA System Administrator role and corresponding data accesses.
Classification Guide: ODNI Classification Guide - 3.3.1 Foreign Intelligence Surveillance Act (FISA)

----

Item: Descriptions of the various FISA roles and corresponding data accesses.
Classification Level: S
Derivative: ODNI FISA S-14
Dissem Control: NOFORN
Reason: 1.4(c)
Declass On: Current date + 25 years
Remarks: Applies to the FISA Analyst, FISA Advanced Analyst, Minimization Approver, Dissemination Nominator, Dissemination Approver, Notification POC, FISA Auditor, FISA System Administrator roles.
Classification Guide: ODNI Classification Guide - 3.3.1 Foreign Intelligence Surveillance Act (FISA)

----

Item: The content of NCTC FISA training.
Classification Level: S
Derivative: ODNI FISA S-14
Dissem Control: NoOFORN
Reason: 1.4 (c)
Declass On: Current date + 25 years
Classification Guide: ODNI Classification Guide - 3.3.1 Foreign Intelligence Surveillance Act (FISA)

----

Item: The fact that ODNI has an active recruitment, assessment, selection, and evaluation process to hire ODNI staff.
Classification Level: U
Classification Guide: ODNI Classification Guide - 3.1.2 Human Resources Management

----

Item: The fact that an overt employee (including their name) works for the ODNI as a staff person, detailee, or contractor
Classification Level: U
Classification Guide: ODNI Classification Guide - 3.1.2 Human Resources Management

----

Item: General information regarding ODNI staff recruitment, assessment, selection, and evaluation process.
Classification Level: U
Classification Guide: ODNI Classification Guide - 3.1.2 Human Resources Management

----

Item: Specific information concerning ODNI staff recruitment, assessment, selection, and evaluation of applicants that reveals information which would allow this process to be circumvented.
Classification Level: S
Derivative: ODNI HRM S-14
Dissem Control: NOFORN
Reason: 1.4(c)
Declass On: Current date + 25 years
Classification Guide: ODNI Classification Guide - 3.1.2 Human Resources Management

----

Item: General information concerning ODNI workforce, mission areas and administrative functions that do not describe the workforce structure in any detail or include, names, titles, assignments or locations.
Classification Level: U
Dissem Control: FOUO
Remarks: Does not include: - Specific number of staff, government and contractors in the operational areas (i.e., IARPA, DDII, NIC, NCTC, NCPC, ONCIX, NIEMA, NIM staffs, and the IC CIO), implying priorities and scope, providing insight into sensitive aspects of operational or sensitive missions areas. - Resource totals. When in doubt, contact DNI-Classification for guidance.
Classification Guide: ODNI Classification Guide - 3.1.2 Human Resources Management

----

Item: Total number of ODNI or IC staff employees authorized or assigned.
Classification Level: S
Derivative: ODNI HRM S-14
Dissem Control: NOFORN
Reason: 1.4(c)
Declass On: Current date + 25 years
OCA: DNI
Remarks: Includes organizational charts where resource numbers can be deduced for the o erational elements within the ODNI.
Classification Guide: ODNI Classification Guide - 3.1.2 Human Resources Management

----

Item: Specific information concerning the existing or planned ODNI (or IC) workforce below the Mission Manager-level that describes the workforce structure including names, resource numbers, assignments or locations, which identifies an organization size and capability, or identifies the resources dedicated to an intelligence objective or geographical area.
Classification Level: S
Derivative: ODNI HRM S-14
Dissem Control: NOFORN
Reason: 1.4(c)
Declass On: Current date + 25 years
OCA: DNI
Remarks: Classified (notional) example: - ONCIX is comprised of 19 staff and 798 contractors working CI and Security related issues. - NCTC is authorized 500 staff billets, and 400 contractors to execute CT functions on behalf of the USG. - DDI I has 122 employees assigned. When in doubt, contact DNl-Classification for guidance.
Classification Guide: ODNI Classification Guide - 3.1.2 Human Resources Management

----

Item: Resource numbers (staff and/or contractor) covering non-operational ODNI elements, such as P&S, PE, AT&F, SRA, CHCO, CFO, CIO/IMD, MSD, ISE, OGC, CLPO, PAO, IC IG, EEOD and OLA, etc.
Classification Level: U
Dissem Control: FOUO
Remarks: FOUO (notional) example: - MSD/HR has 12 staff and 23 contractors. - IC IG has 32 employees assigned. - SRA has 10 staff and 3 detailees assigned. (U) When in doubt, contact DNl-Classification for guidance.
Classification Guide: ODNI Classification Guide - 3.1.2 Human Resources Management

----

Item: The aggregate listing of names and official titles of ODNI employees.
Classification Level: S
Derivative: ODNI HRM S-14
Dissem Control: NOFORN
Reason: 1.4(c)
Declass On: Current date + 25 years
Remarks: Only applicable from 2007 and later.
Classification Guide: ODNI Classification Guide - 3.1.2 Human Resources Management

----

Item: The aggregate listing of names and official titles of IC employees.
Classification Level: TS
Derivative: ODNI HRM S-14
Dissem Control: NOFORN
Reason: 1.4(c)
Declass On: Current date + 25 years
OCA: DNI
Classification Guide: ODNI Classification Guide - 3.1.2 Human Resources Management

----

Item: The fact that ODNI Headquarters is located within the Liberty Crossing Compound in the Tyson's Comer Area of Virginia.
Classification Level: U
Remarks: Including the physical address ofODNI.
Classification Guide: ODNI Classification Guide - 3.1.3 Location

----

Item: The fact that ODNI operates in facilities other than Liberty Crossing.
Classification Level: U
Classification Guide: ODNI Classification Guide - 3.1.3 Location

----

Item: The name and abbreviation of a specific overt ODNI location in the Washington Metropolitan Area.
Classification Level: U
Remarks: May be FOUO do to aggregation.
Classification Guide: ODNI Classification Guide - 3.1.3 Location

----

Item: The association of the ODNI with a covert location.
Classification Level: C
Derivative: ODNI LOC C-14
Dissem Control: NOFORN
Reason: 1.4(c)
Declass On: Current date + 25 years
Remarks: Refer to specific (covert) agency classification guidance for additional details.
Classification Guide: ODNI Classification Guide - 3.1.3 Location

----

Item: The names and abbreviations of ODNI locations in the Washington Metropolitan Area, both overt and covert.
Classification Level: S
Derivative: ODNI LOC S-14
Dissem Control: NOFORN
Reason: 1.4(c)
Declass On: 25X1 + 50 years
Classification Guide: ODNI Classification Guide - 3.1.3 Location

----

Item: Fact that ODNI relies on the results of IC collection sources and methods in protecting our National Security.
Classification Level: U
Classification Guide: ODNI Classification Guide - 3.3 Collection

----

Item: Information regarding the management activities of a collection program or system that is not associated with a specific collection mission and does not provide any precision or enumeration specific to that mission.
Classification Level: U
Dissem Control: FOUO
Remarks: Includes program organization, management, business processes, relationships, coordination, and oversight. Refer to applicable agency or program classification guide for more detailed guidance.
Classification Guide: ODNI Classification Guide - 3.3 Collection

----

Item: Information concerning IC collection and content acquisition capabilities aimed at foreign media and other publicly available material where disclosure could be detrimental to US collection efforts.
Classification Level: C
Derivative: ODNI COL C-14
Dissem Control: NOFORN
Reason: 1.4 (c)
Declass On: Current date + 25 years
Classification Guide: ODNI Classification Guide - 3.3 Collection

----

Item: Information describing or derived from a US or foreign collection system, program, requirement, or research and development (R&D) effort where disclosure would reveal general US or foreign collection capability, or interest.
Classification Level: S
Derivative: ODNI COL S-14
Dissem Control: NOFORN
Reason: 1.4(c), (g)
Declass On: Current date + 25 years
Remarks: Includes program organization, management, business processes, relationships, coordination, and oversight. Refer to applicable agency or program classification guide for more detailed guidance.
Classification Guide: ODNI Classification Guide - 3.3 Collection

----

Item: Information describing or derived from a US or foreign collection system, program, requirement, or R&D effort where disclosure would hinder US collection.
Classification Level: S
Derivative: ODNI COL S-14
Dissem Control: NOFORN
Reason: 1.4 (c)
Declass On: Current date + 25 years
Remarks: Contact ODNI Partner Engagement (ODNI/PE) for foreign disclosure guidance.
Classification Guide: ODNI Classification Guide - 3.3 Collection

----

Item: lnformation describing or derived from a US or foreign collection system, program, requirement, or R&D effort where disclosure would lessen US intelligence or collection advantage.
Classification Level: S
Derivative: ODNI COL S-14
Dissem Control: NOFORN
Reason: 1.4 (c)
Declass On: Current date + 25 years
Remarks: Contact ODNI Partner Engagement (ODNI/PE) for foreign disclosure guidance.
Classification Guide: ODNI Classification Guide - 3.3 Collection

----

Item: Information describing or derived form a US or oreign collection system, program, requirment, or R&D effort where disclosure would reveal specific US or foreign collection capability, interest, or vulnerability.
Classification Level: TS
Derivative: ODNI COL T-14
Dissem Control: NOFORN
Reason: 1.4(c), (g)
Declass On: Current date + 25 years
Remarks: Contact ODMI Partner Engage,emt ( ODI/PE) for foreign disclosure guidence.
Classification Guide: ODNI Classification Guide - 3.3 Collection

----

Item: Information describing or derived from a US or foreign collection system, program, requirement, or R&D effort where disclosure would result in loss of US collection.
Classification Level: TS
Derivative: ODNI COL T-14
Dissem Control: NOFORN
Reason: 1.4(c), (g)
Declass On: Current date + 25 years
Remarks: Contact ODNJ Partner Engagement (ODNl/PE) for foreign disclosure guidance.
Classification Guide: ODNI Classification Guide - 3.3 Collection

----

Item: Information describing or derived from a US or foreign collection system, program, requirement, or R&D effort where disclosure would reveal specific US or foreign collection capability, interest, or vulnerability, result in loss of US collection, and/or negate US intelligence or collection advantage.
Classification Level: TS
Derivative: ODNI COL T-14
Dissem Control: NOFORN
Reason: 1.4(c), (g)
Declass On: Current date + 25 years
Remarks: Contact ODNI Partner Engagement (ODNI/PE) for foreign disclosure guidance.
Classification Guide: ODNI Classification Guide - 3.3 Collection

----

Item: Fact/existence ofthe Office ofthe Director of National Intelligence (ODNI).
Classification Level: U
Classification Guide: ODNI Classification Guide - 3.1.5 Organization and Assocations

----

Item: Fact that the Director of National Intelligence (DNI) serves as the head of the Intelligence Community (IC).
Classification Level: U
Classification Guide: ODNI Classification Guide - 3.1.5 Organization and Assocations

----

Item: The ODNI senior position titles, acronyms and abbreviations.
Classification Level: U
Classification Guide: ODNI Classification Guide - 3.1.5 Organization and Assocations

----

Item: Fact that DNI serves as principal advisor to the President; the National Security Council, and Homeland Security Council for intelligence matters related to the national security.
Classification Level: U
Classification Guide: ODNI Classification Guide - 3.1.5 Organization and Assocations

----

Item: Fact that DNI directs the implementation ofthe US government's National Intelligence Program (NIP) and special activities as directed by the President.
Classification Level: U
Classification Guide: ODNI Classification Guide - 3.1.5 Organization and Assocations

----

Item: ODNI organization charts that provide the existing or planned structure, positions and names assigned at the DNl, PDDNI, CMO, and/or DDNI/ll level and one level below.
Classification Level: U
Remarks: Includes Chiefs of Staff, Executive-level Offices, Directorates, Centers, Administration, and Mission Managers.
Classification Guide: ODNI Classification Guide - 3.1.5 Organization and Assocations

----

Item: Organization charts that provide specific details on the existing or planned structure of ODNl administrative, support or non-operational areas which include names, resource numbers, assignments or locations
Classification Level: U
Dissem Control: FOUO
Remarks: Includes: P&S, PE, AT&F, SRA, CHCO, CFO, CIO/IMD, ISE, OGC, CLPO, PAO, re IG, EEOD and OLA, etc. When in doubt, contact DNI-Classification for guidance.
Classification Guide: ODNI Classification Guide - 3.1.5 Organization and Assocations

----

Item: Organization charts that provide specific details on the existing or planned structure of ODNl operational components at the third organizational level and below to include names, resource numbers, assignments or locations.
Classification Level: S
Derivative: ODNI ORG S-14
Dissem Control: NOFORN
Reason: 1.4(c)
Declass On: Current date plus 25 years
Remarks: Includes: IARPA, DDII, NIC, NCTCm NCPC, ONCIX, NIEMA, NIM stafss, and the IC CIO, etc. When in doubt, contact DNI-Classification for guidance.
Classification Guide: ODNI Classification Guide - 3.1.5 Organization and Assocations

----

Item: Fact that ODNI employs CIA, FBI, NSA, OHS, DoS or other USG agency personnel (permanent staff or detailees) within the LX Compound, with no other details. ORG S-14
Classification Level: U
Classification Guide: ODNI Classification Guide - 3.1.5 Organization and Assocations

----

Item: The fact that there are NIMs dedicated to specific countries or areas of responsibility.
Classification Level: U
Classification Guide: ODNI Classification Guide - 3.1.5 Organization and Assocations

----

Item: The fact that NIMs produce Unifying Intelligence Strategies (UIS).
Classification Level: U
Classification Guide: ODNI Classification Guide - 3.1.5 Organization and Assocations

----

Item: The fact that that NIMs produce UIS' for Counterterrorism (CT) and Counterproliferation (CP).
Classification Level: U
Classification Guide: ODNI Classification Guide - 3.1.5 Organization and Assocations

----

Item: The fact of a named regionally or functionally focused UIS, other than Counterterrorism or Counterproliferation.
Classification Level: U
Dissem Control: FOUO
Classification Guide: ODNI Classification Guide - 3.1.5 Organization and Assocations

----

Item: The fact of a UIS that focuses on a named country.
Classification Level: U
Dissem Control: FOUO
Classification Guide: ODNI Classification Guide - 3.1.5 Organization and Assocations

----

Item: The fact ofa UIS that focuses on a named topic, a u FOUO component thereof, Ione actor or non-state actor.
Classification Level: U
Dissem Control: FOUO
Remarks: Classification may be hugher deoending on the specific topic or named actor.
Classification Guide: ODNI Classification Guide - 3.1.5 Organization and Assocations

----

Item: General information regarding an overt contract that does not provide insight into capabilities, vulnerabilities, or intelligence sources or methods.
Classification Level: U
Remarks: May require PROPIN or be Contract Sensitive.
Classification Guide: ODNI Classification Guide - 3.1.6 Procurement

----

Item: General information regarding an covert contract that does not provide insight into capabilities, vulnerabilities, or intelligence sources or methods.
Classification Level: C
Derivative: ODNI Prop C-14
Dissem Control: NOFORN
Reason: 1.4(c)
Declass On: 25X1+50 years
Remarks: Refer to appropriate procurment agency for guidance.
Classification Guide: ODNI Classification Guide - 3.1.6 Procurement

----

Item: The fact that ODNI manages national intelligence requirements.
Classification Level: U
Remarks: Includes Transnational Crime Strategy requirements .
Classification Guide: ODNI Classification Guide - 3.4.1 Requirements Management

----

Item: General ODNI customer requirements.
Classification Level: U
Dissem Control: FOUO
Remarks: May be classified based on content
Classification Guide: ODNI Classification Guide - 3.4.1 Requirements Management

----

Item: General information concerning customer requirements which reveals US intelligence activities, capabilities, targets, sources, or methods.
Classification Level: C
Derivative: ODNI REQ C-14
Dissem Control: REL TO USA. FVEY
Reason: 1.4(c)
Declass On: Current date+ 25 years
Remarks: May be NOFORN depending on content. Includes support for military, policy & diplomatic, maritime and aviation, Homeland Security and law enforcement intelligence requirements.
Classification Guide: ODNI Classification Guide - 3.4.1 Requirements Management

----

Item: Specific information concerning customer requirements which reveals US intelligence activities, capabilities, targets, sources, or methods.
Classification Level: S
Derivative: ODNI REQ S-14
Dissem Control: REL TO USA. FVEY
Reason: 1.4(c)
Declass On: Current date+ 25 years
Remarks: May be NOFORN depending on content. Includes support for military, policy & diplomatic, maritime and aviation, Homeland Security and law enforcement intelligence requirements.
Classification Guide: ODNI Classification Guide - 3.4.1 Requirements Management

----

Item: Specific information concerning an intelligence collection program and capability to adress a specific consumer requirment(s).
Classification Level: TS
Derivative: ODNI REQ T-14
Dissem Control: REL TO USA. FVEY
Reason: 1.4(c)
Declass On: Current date+ 25 years
Remarks: Includes: - support for military - policy & diplomatic - maritime and aviation - Homeland security - Law enforcement intelligence requirements. May be NOFORN depending on participants and specific information. Contact ODNI Partner Engagement (ODNl/PE) for foreign disclosure guidance.
Classification Guide: ODNI Classification Guide - 3.4.1 Requirements Management

----

Item: Individually unclassified or controlled unclassified data items that in the compilation or aggregation would provide insight into ODNl's or IC's organization, functions, staffing, activities, capabilities, vulnerabilities, or intelligence sources or methods.
Classification Level: C
Derivative: ODNI MOS C-14
Dissem Control: NOFORN
Reason: 1.4(c)
Declass On: Current date + 25 years
Remarks: May be REL TO USA, FVEY depending on the issue. Contact ODNI Partner Engagement (ODNl/PE) for guidance.  Example I. Work products must be examined from an outsider's perspective to ensure adversaries cannot derive classified information from various unclassified sources. Unclassi tied "puzzle pieces" can sometimes be assembled to form a classified "picture" or unintemionally paint a red X on a weak spot in your ability to perform or maintain your mission at acceptable levels. Example 2: Unclassified budget information could be paired with other unclassified acquisition or requirements information to show an agency's vulnerability or shortfall in protection mechanisms for IT or physical security systems.  Example 3: We would not want our adversaries to know that we did not properly budget to provide 2417 police coverage ofthe entry points to the faci lity or to purchase necessary equipment to secure all building entry points. These vulnerabilities could be exploited to gain access to the building.
Classification Guide: ODNI Classification Guide - 3.1.4 Aggregation or Mosaic

----

Item: General information on analytic methodologies for sensitive data sets.
Classification Level: C
Derivative: ODNI ANA C-14
Dissem Control: REL TO USA. FVEY
Reason: 1.4(C), (g)
Declass On: Current date + 25 years
Remarks: Does not include specifically authorized documents produced by NCTC or the NIC as pan of USG specific analyses or assessments which are unclassified for FOUO.
Classification Guide: ODNI Classification Guide - 3.2 Analysis

----

Item: Intelligence analysis that provides general information regarding sensitive or classified collection systems or data sets, or intelligence sources and methods.
Classification Level: C
Derivative: ODNI ANA C-14
Dissem Control: REL TO USA. FVEY
Reason: 1.4(c)
Declass On: Current date + 25 years
Remarks: May contain companmented information. Refer to appropriate Program Security Officer I Program Security Guide for additional information.
Classification Guide: ODNI Classification Guide - 3.2 Analysis

----

Item: Intelligence analysis that provides specific information regarding sensitive or classified collection systems or data sets, or intelligence sources and methods.
Classification Level: S
Derivative: ODNI ANA S-14
Dissem Control: REL TO USA. FVEY
Reason: 1.4(c)
Declass On: Current date + 25 years
Classification Guide: ODNI Classification Guide - 3.2 Analysis

----

Item: Intelligence analysis that provide specific information regarding sesitive or calssified collection systems or data sts, or intelligence sources and methods which if revealed, would dllify or measurable reduce their effectiveness.
Classification Level: TS
Derivative: ODNI ANA T-14
Dissem Control: NOFORN
Reason: 1.4(c)
Declass On: Current date + 25 years
Remarks: Contact ODNI Panner Engagement (ODNl/PE) for foreign disclosure guidance.
Classification Guide: ODNI Classification Guide - 3.2 Analysis

===== End ODNI Classification Guide =====

Below are three explicit examples of the classification process:

=====Example 1:

Input: Internal ODNI briefing slides detailing quarterly reallocation of NIP contingency funds in response to unanticipated foreign HUMINT disruptions. Includes line-item transfers across black program budgets, updated burn rates for regional counterintelligence cells, classified vendor disbursement codes, and an appendix on temporary clearance waivers authorized for expedited procurement.

Output:
Classification: **TS NOFORN**

Item: Detailed information regarding ODNI and IC fiscal matters inclusive of budget, manpower, expenditures, funding, and appropriations data, to include related guidance, procedures, agreements, vulnerabilities, or disbursement techniques related to the National Intelligence Program (NIP), or the financial condition and resources ofthe IC as a whole.
Level: TS
Derivative: ODNI FIN T-14
Dissem Control: NOFORN
Reason: 1.4(c)
Declass On: Current date + 25 years
OCA: N/A
Remarks: A higher classification or additional markings may be required for compartmented information or programs. Consult with appropriate Program Compartment Guide or NCIX for compartmented info.

=====End Example 1

=====Example 2:

Input: The ODNI operates facilities such as the overt National Intelligence Fusion Center (NIFC) in Crystal City, Virginia, and the covert Subterranean Analytic Compound (SAC) beneath the Pentagon, while the Langley-Oxon Run Intelligence Nexus (LORIN) in McLean and Anacostia River Technical Operations Site (ARTOS) support Counterterrorism (CT) and Counterproliferation (CP) missions through Unified Intelligence Summaries (UIS) produced by National Integration Modules (NIMs).

Output:
Classification: **S NOFORN**

Item: The names and abbreviations of ODNI locations in the Washington Metropolitan Area, both overt and covert.
Level: S
Derivative': ODNI LOC S-14
Dissem Control: NOFORN
Reason: 1.4(c)
Declass On: 25X1 + 50 years
OCA:
Remarks:
Classification Guide: ODNI Classification Guide - 3.1.3 Location


Item: The fact that that NIMs produce UIS' for Counterterrorism (CT) and Counterproliferation (CP).
Level: U
Dissem Control: 
Reason: 
Declass On: 
OCA: 
Remarks: 
Classification Guide: ODNI Classification Guide - 3.1.5 Organization and Assocations

=====End Example 2

=====Example 3:

Input: Hi John, I was curious if you'd like to meet me for lunch at noon in the cafeteria. I have a few personal things I'd like to discuss with you, like my recent separation and some health concerns that have popped up. You available?

Output:
Unable to determine classification from the Classification Guide.

=====End Example 3

Classify the new input below using only the Classification Guide above as in the examples. 
If the input corresponds to multiple items in the classification guide, please return all of the corresponding items and use the highest classification level and dissem control found in the corresponding items to make the classification decision. If you are unable to determine the classification from information in the Classification Guide, please respond with 'Unable to determine classification from the Classification Guide.' Please include NO ADDITIONAL TEXT in your response.'

New Input:
"""

#odel = Model(url=MODEL_URL, pat=CLARIFAI_PAT)
#print("CLARIFAI_PAT:", CLARIFAI_PAT)  # Debugging line to check if the PAT is loaded correctly

# Predefined model list (can be expanded)
MODEL_MAP = {
    "Claude 3.5 Sonnet": "https://clarifai.com/anthropic/completion/models/claude-3_5-sonnet",
    "GPT OSS 120B": "https://clarifai.com/openai/chat-completion/models/gpt-oss-120b",
    "GPT 4o": "https://clarifai.com/openai/chat-completion/models/gpt-4o",
    "Grok 3": "https://clarifai.com/xai/chat-completion/models/grok-3",
    "Llama 3.2 (3B)": "https://clarifai.com/meta/Llama-3/models/Llama-3_2-3B-Instruct",
    "Gemma 3 (12B)-it": "https://clarifai.com/gcp/generate/models/gemma-3-12b-it",
    "Qwen 2.5-VL-7B-Instruct": "https://clarifai.com/qwen/qwen-VL/models/Qwen2_5-VL-7B-Instruct",
    "Phi-4": "https://clarifai.com/microsoft/text-generation/models/phi-4",
    "Qwen QwQ-32B" : "https://clarifai.com/qwen/qwenLM/models/QwQ-32B-AWQ",
}


# Predefined model list (can be expanded)
CLASSIFICATION_MAP = {
    "ODNI Classification Guide Version 2.1" : "ODI_PROMPT",
}



@st.cache_resource
def get_model(model_url):
    return Model(url=model_url, pat=CLARIFAI_PAT)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1))
def stream_prediction(prompt):
    """Enhanced streaming generator with error handling"""
    if not CLARIFAI_PAT:
        yield "🔑 Error: Missing Clarifai PAT in secrets"
        return

    try:
        # Initialize the model
        #model = Model(url=MODEL_URL, pat=CLARIFAI_PAT)
        MODEL_URL = st.session_state.model_url
        print(f"MODEL_URL: {MODEL_URL}")  # Debugging line to check the model URL
        model=get_model(MODEL_URL)
        
        
        print(f"temp: {st.session_state.temperature}")
        print(f"max_tokens: {st.session_state.max_tokens}")
        print(f"top_p: {st.session_state.top_p}")
        
        stream = model.generate_by_bytes(
            input_bytes=prompt.encode(),
            input_type="text",
            inference_params={
                "temperature": st.session_state.temperature,
                "max_tokens": st.session_state.max_tokens,
                "top_p": st.session_state.top_p
            }
        )

        buffer = ""
        for chunk in stream:
            #print(chunk)  # Debugging line to check the chunk content
            status_code = chunk.status.code
            #print(status_code)  # Debugging line to check the status code
            if status_code == 10000:
                text_chunk = chunk.outputs[0].data.text.raw
                buffer += text_chunk
                
                # Flush buffer on sentence boundaries
                if len(buffer) > 30 or any(punct in buffer for punct in ".!?"):
                    yield buffer
                    buffer = ""
                    time.sleep(0.02)  # Simulate natural typing speed
            else:
                yield f"⚠️ Error: {chunk.status.description}"
        
        if buffer:  # Final flush
            yield buffer

    except Exception as e:
        non_stream = model.predict_by_bytes(
            input_bytes=prompt.encode(),
            input_type="text",
            inference_params={
                "temperature": st.session_state.temperature,
                "max_tokens": st.session_state.max_tokens,
                "top_p": st.session_state.top_p
            }
        )
        response = non_stream.outputs[0].data.text.raw
        yield response


# UI Setup
st.set_page_config(page_title="ClassifAI Chat", layout="wide")
st.title("ClassifAI ")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

# Sample inputs for demonstration
sample_inputs2 = [
    {
        "title": "🔒 Classified Document Example",
        "description": "Intelligence analysis that provide specific information regarding sensitive or classified collection systems ",
        "text": "A recent intelligence analysis conducted at the ODNI Headquarters within the Liberty Crossing Compound in Tyson's Corner, Virginia, identified vulnerabilities in the STARFALL satellite system's data transmission protocols, which if exploited, could compromise real-time surveillance of adversarial communications in the Redshift-9 frequency band. The Director of National Intelligence personally authorized limited dissemination of this finding to prevent adversaries from adapting their encryption methods, as the STARFALL system remains the IC's primary tool for intercepting high-priority targets."
    },
    {
        "title": "🏢 Facility Information",
        "description": "ODNI locations and operations",
        "text": "The ODNI operates facilities such as the overt National Intelligence Fusion Center (NIFC) in Crystal City, Virginia, and the covert Subterranean Analytic Compound (SAC) beneath the Pentagon, while the Langley-Oxon Run Intelligence Nexus (LORIN) in McLean and Anacostia River Technical Operations Site (ARTOS) support Counterterrorism (CT) and Counterproliferation (CP) missions through Unified Intelligence Summaries (UIS) produced by National Integration Modules (NIMs)."
    },
    {
        "title": "👥 General information regarding an overt contract",
        "description": "Contract information",
        "text": "Contract #DOD-LOG-2023-09876 between the U.S. Department of Defense and Global Logistics Solutions Inc. authorizes the provision of supply chain management services for non-sensitive military installations in the continental United States, effective March 15, 2024, through March 14, 2027, with a total value of $125 million and annual performance reviews conducted by the Defense Contract Management Agency."
    },
    {
        "title": "💬 Personal Message",
        "description": "Non-classified personal communication",
        "text": "Hi John, I was curious if you'd like to meet me for lunch at noon in the cafeteria. I have a few personal things I'd like to discuss with you, like my recent separation and some health concerns that have popped up. You available?"
    }
]

sample_inputs = [
    {
        "title": "🛰️ Secure Intelligence Dissemination and Collection Systems",
        "description": "Details on the Secure Intelligence Dissemination Protocol (SIDP), TS/SCI clearance, and the STRATOSPHERE-11 SIGINT system used for monitoring high-value targets.",
        "text": "Under the Secure Intelligence Dissemination Protocol (SIDP), NCTC analysts with Top Secret/Sensitive Compartmented Information (TS/SCI) clearance access unminimized FISA-derived data through the classified Fusion Analytics Gateway (FAG-9), requiring dual authentication via a DoD Common Access Card and a dynamic PIN generated by the NCTC’s Automated Security Validation Interface (ASVI). An ongoing analysis of SIGINT from the codenamed STRATOSPHERE-11 system—deployed aboard high-altitude aerostats over Southwest Asia—reveals near-real-time UHF radio traffic patterns used by HVTs, but exposure of the system’s passive geolocation capabilities (operating at 275 MHz with ±5 meter precision) would enable adversarial countermeasures, diminishing its operational advantage for 18–24 months."
    },
    {
        "title": "🔍 NCTC FISA Auditor Operations",
        "description": "Describes the role of the NCTC's covert team of FISA Auditors in reviewing surveillance applications and ensuring compliance with minimization protocols.",
        "text": "The NCTC's Intelligence Surveillance Division employs a covert team of eight FISA Auditors, tasked with reviewing all Section 702 and 1881a surveillance applications submitted by federal agencies, ensuring compliance with minimization protocols by cross-referencing metadata from intercepted international calls and encrypted messaging platforms against a centralized watchlist database, with noncompliant cases flagged for re-evaluation by the FISA Court's Technical Advisory Board."
    },
    {
        "title": "👥 ODNI and NCTC Recruitment and Personnel Roles",
        "description": "Outlines the recruitment process for ODNI analysts, including the SACE exam and Director's Nominations, and details specific roles like FISA Dissemination Approvers at the NCTC.",
        "text": "The ODNI recruits analysts through a process requiring passage of the Strategic Analysis Competency Exam (SACE), with select candidates fast-tracked by Director’s Nominations (DN) if they possess “priority skills” like Russian linguistics or HUMINT expertise, while senior roles such as Deputy Director for Integration (DDI) or Chief of Staff (COS) require TS/SCI clearance and approval from the Recruitment Validation Board (RVB), which meets quarterly on the third Tuesday; concurrently, NCTC’s Counterterrorism Collaboration Unit (CCTU) employs FISA Dissemination Approvers (FDA) at the GS-14 level to authorize Section 702 data sharing, a role often filled by analysts with prior NSA or FBI experience."
    },
    {
        "title": "📋 Department of Defense Logistics Contract",
        "description": "Details of contract #DOD-LOG-2023-09876 for supply chain management services for non-sensitive military installations in the United States.",
        "text": "Contract #DOD-LOG-2023-09876 between the U.S. Department of Defense and Global Logistics Solutions Inc. authorizes the provision of supply chain management services for non-sensitive military installations in the continental United States, effective March 15, 2024, through March 14, 2027, with a total value of $125 million and annual performance reviews conducted by the Defense Contract Management Agency."
    },
    {
        "title": "📊 ODNI Intelligence Aggregation and Analysis",
        "description": "Describes how the aggregation of publicly accessible data, such as workforce reports and budget line items, can reveal ODNI operational priorities and capabilities.",
        "text": "The Office of the Director of National Intelligence (ODNI) oversees the National Intelligence Program, with its Counterterrorism Center (NCTC) maintaining FISA Notification Points of Contact (POCs) to coordinate intelligence sharing under Section 106 of the FISA Amendments Act. Aggregating publicly accessible data—such as annual ODNI workforce reports listing 1,243 intelligence analysts assigned to counterproliferation tasks, budget line items for \"Project Sentinel\" totaling $87M in FY2023, and unclassified training records indicating 348 IC employees completed Russian language courses in 2022—reveals operational priorities and capabilities tied to monitoring nuclear programs in Central Asia."
    },
    {
        "title": "🕳️ Covert ODNI Analytical Hub Operations",
        "description": "Information on a covert ODNI hub, codenamed 'Neon Valley,' processing geospatial and signals intelligence, and how aggregated public data reveals its mission.",
        "text": "The Office of the Director of National Intelligence (ODNI) maintains a covert analytical hub, codenamed \"Neon Valley,\" located beneath a disused solar farm in Nevada, which processes geospatial and signals intelligence data from East Asia and the Pacific. Customer requirements for real-time maritime domain awareness, coupled with frequent requests for assessments of submarine cable vulnerabilities, indicate reliance on undersea SIGINT collection methods and partnerships with private telecommunications firms. Aggregated data from public ODNI job postings for Mandarin linguists, procurement records for custom RF shielding materials, and satellite imagery analysis contracts reveal staffing priorities, technical capabilities, and operational focus areas linked to the facility’s mission."
    },
    {
        "title": "⚖️ NCTC FISA Minimization Approvers",
        "description": "Information on the role of NCTC's FISA Minimization Approvers in reviewing retention protocols for incidental U.S. person communications.",
        "text": "The National Counterterrorism Center (NCTC) maintains a team of three senior analysts designated as FISA Minimization Approvers, established under Section 105B of the Foreign Intelligence Surveillance Act in 2018, responsible for reviewing and approving retention protocols for incidental U.S. person communications collected during counterterrorism surveillance operations directed at targets in Yemen and Somalia."
    },

    {
        "title": "💬 Personal Message",
        "description": "Non-classified personal communication",
        "text": "Hi John, I was curious if you'd like to meet me for lunch at noon in the cafeteria. I have a few personal things I'd like to discuss with you, like my recent separation and some health concerns that have popped up. You available?"
    }
]




# Display sample input cards
if not st.session_state.messages:  # Only show when chat is empty
    st.subheader("Try these sample inputs:")
    
    # Process samples in pairs to ensure proper row alignment
    for i in range(0, len(sample_inputs), 2):
        cols = st.columns(2)
        
        # Left column
        with cols[0]:
            if i < len(sample_inputs):
                sample = sample_inputs[i]
                with st.container():
                    st.markdown(f"**{sample['title']}**")
                    description = sample['description'][:150] + "..." if len(sample['description']) > 150 else sample['description']
                    st.caption(description)
                    if st.button(f"Use this example", key=f"sample_{i}", use_container_width=True):
                        # Add user message to history
                        st.session_state.messages.append({"role": "user", "content": sample['text']})
                        st.rerun()
                    
                    # Show preview of text
                    with st.expander("Preview"):
                        st.text(sample['text'][:250] + "..." if len(sample['text']) > 250 else sample['text'])
        
        # Right column
        with cols[1]:
            if i + 1 < len(sample_inputs):
                sample = sample_inputs[i + 1]
                with st.container():
                    st.markdown(f"**{sample['title']}**")
                    description = sample['description'][:150] + "..." if len(sample['description']) > 150 else sample['description']
                    st.caption(description)
                    if st.button(f"Use this example", key=f"sample_{i+1}", use_container_width=True):
                        # Add user message to history
                        st.session_state.messages.append({"role": "user", "content": sample['text']})
                        st.rerun()
                    
                    # Show preview of text
                    with st.expander("Preview"):
                        st.text(sample['text'][:250] + "..." if len(sample['text']) > 250 else sample['text'])

        # Add spacing between rows
        st.markdown("---")

# Display previous messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Handle new input
prompt = None
if user_input := st.chat_input("Message Clarifai"):
    # Add user message to history and display immediately
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)
    prompt = user_input

# Check if we need to process the last message (for sample inputs)
elif st.session_state.messages:
    # Check if the last message is a user message that hasn't been processed yet
    if (len(st.session_state.messages) % 2 == 1 and 
        st.session_state.messages[-1]["role"] == "user"):
        prompt = st.session_state.messages[-1]["content"]

# Process message if needed
if prompt:
    
    # Display assistant response
    with st.chat_message("assistant"):
        
        # Show spinner while generating response
        #with st.spinner("Assistant is thinking..."):
        with st_lottie_spinner(lottie_json, key="thinking", speed=1, width=200, height=200):    

            message_placeholder = st.empty()
            full_response = ""
            
            # Stream response with typing indicator
            for chunk in stream_prediction(ODI_PROMPT + prompt):
                full_response += chunk
                full_response = full_response.replace('\n','  \n')
                
                message_placeholder.markdown(f"{full_response}▌")
            
            # Final render without cursor
            full_response = full_response.replace('\n','  \n')
            message_placeholder.markdown(f"{full_response}")
    
    # Add assistant response to history
    st.session_state.messages.append({"role": "assistant", "content": full_response})


      
# Sidebar Configuration
with st.sidebar:
    st.title("Model Settings")
    
    
        # Model selection
    selected_classification = st.selectbox(
        "Choose Classification Guide",
        list(CLASSIFICATION_MAP.keys()),
        index=0
    )
    
    # Model selection
    selected_model = st.selectbox(
        "Choose LLM",
        list(MODEL_MAP.keys()),
        index=0
    )
    
    
    st.session_state.model_url = MODEL_MAP[selected_model]
    print(f"model_url: {st.session_state.model_url}")  # Debugging line to check the model URL
    
    # Inference parameters
    st.session_state.temperature = st.slider(
        "Creativity (Temperature)",
        0.0, 2.0, 0.0
    )
    st.session_state.max_tokens = st.slider(
        "Max Response Length",
        100, 5000, 2000
    )
    st.session_state.top_p = st.slider(
        "Focus (Top-P)",
        0.1, 1.0, 0.9
    )
    
    # Clear chat button
    st.markdown("---")
    if st.button("🗑️ Clear Chat", use_container_width=True, type="secondary"):
        st.session_state.messages = []
        st.rerun()
    
    # Show message count
    st.caption(f"Messages: {len(st.session_state.messages)}")
    
    #st.subheader("Debug Info")
    #st.write(f"Message count: {len(st.session_state.messages)}")
    #if st.session_state.messages:
    #    st.write("Last message:", st.session_state.messages[-1]["content"][:50] + "...")