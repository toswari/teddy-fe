# imports
import streamlit as st
import ast
import base64
import io
import requests
import urllib

from clarifai.client.app import App
from clarifai.client.auth import create_stub
from clarifai.client.auth.helper import ClarifaiAuthHelper
from clarifai.client.input import Inputs
from clarifai.client.model import Model
from clarifai.client.user import User
from clarifai.modules.css import ClarifaiStreamlitCSS
from clarifai_grpc.grpc.api import resources_pb2, service_pb2

from concurrent.futures import ThreadPoolExecutor, as_completed
from google.protobuf.json_format import MessageToDict
from google.protobuf.struct_pb2 import Struct
from PIL import Image, ImageDraw, ImageFont

from annotated_text import annotated_text
from streamlit_image_select import image_select

# streamlit config
st.set_page_config(layout="wide")
ClarifaiStreamlitCSS.insert_default_css(st)

# setup
auth = ClarifaiAuthHelper.from_streamlit(st)
stub = create_stub(auth)
userDataObject = auth.get_user_app_id_proto()


##########################
#### HELPER FUNCTIONS ####
##########################

def hex_to_rgb(hex_code):
  """Convert hex color code to RGB tuple."""
  hex_code = hex_code.lstrip('#')
  return tuple(int(hex_code[i:i+2], 16) for i in (0, 2, 4))

def luminance(hex_code):
  """Calculate the relative luminance of a color."""
  rgb = hex_to_rgb(hex_code)
  # Normalize the RGB values by dividing by 255
  normalized_rgb = [x / 255.0 for x in rgb]
  
  # Apply the sRGB luminance formula
  def linearize(value):
      if value <= 0.03928:
          return value / 12.92
      else:
          return ((value + 0.055) / 1.055) ** 2.4
  
  r, g, b = [linearize(v) for v in normalized_rgb]
  
  # Calculate the luminance
  return 0.2126 * r + 0.7152 * g + 0.0722 * b

def is_light_or_dark(hex_code):
  """Determine whether the color is light or dark."""
  lum = luminance(hex_code)
  return "light" if lum > 0.5 else "dark"

def text_color_for_background(hex_code):
  """Determine the appropriate text color (white or black) for a given background color."""
  return "#000000" if is_light_or_dark(hex_code) == "light" else "#ffffff"

def footer(st):
  with open('footer.html', 'r') as file:
    footer = file.read()
    st.write(footer, unsafe_allow_html=True)

def call_apparel_model(pic, conf, selected_color, line_thickness, userDataObject, metadata, stub):
  # Get the width and the height of the image
  with st.spinner("Detecting apparel type in picture!"):
    image = Image.open(urllib.request.urlopen(pic))
    width, height = image.size

    post_model_outputs_response = stub.PostModelOutputs(
      service_pb2.PostModelOutputsRequest(
        user_app_id = userDataObject,
        model_id = MODEL_ID,
        version_id = MODEL_VERSION_ID,  # This is optional. Defaults to the latest model version
        inputs = [
          resources_pb2.Input(
            data=resources_pb2.Data(
              image=resources_pb2.Image(
                url=pic)))]
      ),
      metadata=metadata
    )

    # Since we have one input, one output will exist here
    output = post_model_outputs_response.outputs[0]

    # filter app returns for only select concepts
    select_concepts = [
      "dress",
      "outerwear",
      "pants",
      "shorts",
      "skirt",
      "top",
      "suit"
    ]

    filtered_outout_regions = [x for x in output.data.regions if x.data.concepts[0].name in select_concepts]

    apparel_return = []

    for detection in filtered_outout_regions:
      top_row = detection.region_info.bounding_box.top_row
      left_col = detection.region_info.bounding_box.left_col
      bottom_row = detection.region_info.bounding_box.bottom_row
      right_col = detection.region_info.bounding_box.right_col

      for concept in detection.data.concepts:
        if concept.value >= conf/100.0:

          apparel_return.append({
            "type": concept.name, 
            "confidence": concept.value,
            "width": width,
            "height": height,
            "top_row": top_row,
            "left_col": left_col,
            "bottom_row": bottom_row,
            "right_col": right_col
          })

      img1 = ImageDraw.Draw(image)

      line_passes = 1
      if line_thickness == 'Medium':
        line_passes = 3
      elif line_thickness == 'Thick':
        line_passes = 6

      for mtch in apparel_return:
            
        # create rectangle image
        h1 = mtch["top_row"]    * height
        w1 = mtch["left_col"]   * width
        h2 = mtch["bottom_row"] * height
        w2 = mtch["right_col"]  * width

        img1.rectangle((w1, h1, w2, h2), width=line_passes, outline=selected_color)

        # calculate font size based off of image height
        fontsize = int(image.height / 40)
        font = ImageFont.truetype("arial.ttf", fontsize)

        # white dropshadow - note: this is actually swapped with the below. mt
        img1.text(
          (w1 + 0 + line_passes, h1 + 0 + line_passes),
          mtch["type"],
          align ="left",
          fill=selected_color,
          font=font
        )

        # selected color - note: this is actually swapped with the above. mt
        img1.text(
          (w1 + 1 + line_passes, h1 + 1 + line_passes),
          mtch["type"],
          align ="left",
          fill='white',
          font=font
        )

  with st.expander(label="Apparel Detections", expanded=True):
    
    max_height = 10000
    if image.height > max_height:
      new_height = max_height
    else:
      new_height = image.height
          
    new_width = int(new_height * image.width / image.height)
    resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    st.image(resized_image)

    return apparel_return

def post_visual_search(stub, user_app_id, search_id, matches_to_show, temp_im_bytes, metadata, concept=None):

  concepts_to_dataset = {
    'pants': 'pants',
    'top': 'tops'
  }
  
  if concept not in concepts_to_dataset.keys():
    res_pvs = stub.PostInputsSearches(
      service_pb2.PostInputsSearchesRequest(
        user_app_id = user_app_id,
        pagination = service_pb2.Pagination(
          per_page = matches_to_show
        ),
        searches = [
          resources_pb2.Search(
            id = search_id,
            query = resources_pb2.Query(
              ranks = [
                resources_pb2.Rank(
                  annotation = resources_pb2.Annotation(
                    data = resources_pb2.Data(
                      image = resources_pb2.Image(
                        base64 = temp_im_bytes))))]))]
      ),
      metadata = metadata)
    return res_pvs

  else:
    dataset_to_filter = concepts_to_dataset[concept]

    res_pvs = stub.PostInputsSearches(
      service_pb2.PostInputsSearchesRequest(
        user_app_id = user_app_id,
        pagination = service_pb2.Pagination(
          per_page = matches_to_show
        ),
        searches = [
          resources_pb2.Search(
            id = search_id,
            query = resources_pb2.Query(
              ranks = [
                resources_pb2.Rank(
                  annotation = resources_pb2.Annotation(
                    data = resources_pb2.Data(
                      image = resources_pb2.Image(
                        base64 = temp_im_bytes))))
              ],
              filters = [
                resources_pb2.Filter(
                  input = resources_pb2.Input(
                    dataset_ids = [dataset_to_filter]))]))]
      ),
      metadata = metadata)

    return res_pvs

def call_visual_search(pic, conf, app_return, matches_to_show, stub, metadata, userDataObject):
  
  with st.spinner("Running visual search on crops:"):

    image = Image.open(urllib.request.urlopen(pic))

    items = []

    for apparel in app_return:
      left   = apparel["left_col"]   * apparel["width"]
      top    = apparel["top_row"]    * apparel["height"]
      right  = apparel["right_col"]  * apparel["width"]
      bottom = apparel["bottom_row"] * apparel["height"]
      
      im1 = image.crop((left, top, right, bottom))
      area = (right - left) * (bottom - top)
      items.append({
        "type": apparel["type"],
        "confidence": apparel["confidence"],
        "crop": im1,
        "area": area
      })
        
    if len(items) == 0:
      st.write("We're sorry; we were not able to find any high quality matches with the Clarifai Apparel Model.  Please try again!")
      return

    # run predicts on crops
    temp_results = {}
    threads = []
    end_results = []

    with ThreadPoolExecutor(max_workers = 10) as executor:
      for idx,item in enumerate(items):

        search_id = str(idx)
        concept = item['type']

        # get crop
        temp_im_bytes = io.BytesIO()
        item['crop'].save(temp_im_bytes, format='PNG')
        temp_im_bytes = temp_im_bytes.getvalue()

        # filter down based off of concept
        threads.append(executor.submit(post_visual_search, stub, userDataObject, search_id, matches_to_show, temp_im_bytes, metadata, concept))
        
        # parse results
        temp_results[search_id] = {'crop': item['crop'], 'concept': concept}

      for task in as_completed(threads):

        search_id = task.result().searches[0].id
        im_crop = temp_results[search_id]['crop']
        concept = temp_results[search_id]['concept']
        hits = task.result().hits

        temp_dict = {
          'search_id': search_id,
          'im_crop': im_crop,
          'concept': concept,
          'hits': hits
        }

        end_results.append(temp_dict)

  return end_results

def get_url_list(m_ids, stub, metadata, userDataObject):
  url_list = []
  for id in m_ids:
    get_input_response = stub.GetInput(
      service_pb2.GetInputRequest(
        user_app_id=userDataObject, 
        input_id=id
      ),
      metadata=metadata
    )

    # if get_input_response.status.code != status_code_pb2.SUCCESS:
    #   print(get_input_response.status)
    #   raise Exception("Get input failed, status: " + get_input_response.status.description)

    url_list.append(get_input_response.input.data.image.url)

  return url_list


####################
####  SIDEBAR   ####
####################

#### Page Display Options
with st.sidebar:

  st.caption('Below options are mostly here to help customize any displayed graphics/text.')

  #### main header display
  with st.expander('Header Setup'):

    company_logo = st.text_input(label = 'Banner Url', value = 'https://upload.wikimedia.org/wikipedia/commons/b/bc/Clarifai_Logo_FC_Web.png')
    company_logo_width = st.slider(label = 'Banner Width', min_value = 1, max_value = 1000, value = 300)
    page_title = st.text_input(label='Module Title', value='Digital Asset Management and Personalization Demo')

  #### Digital Asset Management Options
  with st.expander('Digital Asset Management'):

    dam_subheader_title = st.text_input(label = 'DAM subheader title', value = '✨ Leveraging Clarifai for Digital Asset Management & Metadata Tagging ✨')
    dam_default_image = st.text_input(label = 'DAM default example image', value = 'https://s3.amazonaws.com/samples.clarifai.com/dam_demo_kenneth.jpeg')
  
    st.subheader('Model Selections')
    
    # Visual Classifier Selection
    try:
      print("🔍 DEBUG: Fetching visual-classifier models...")
      print(f"🔍 DEBUG: PAT: {auth._pat[:20]}...")
      print(f"🔍 DEBUG: User ID: {userDataObject.user_id}")
      print(f"🔍 DEBUG: App ID: {userDataObject.app_id}")
      
      # Use User class to browse all community models
      user_client = User(pat=auth._pat)
      print("🔍 DEBUG: User instance created for community browsing")
      
      # List all public models with filter - get as dicts to avoid deprecated model errors
      models_data = user_client.list_models(
        user_id="all",
        show=False,
        return_clarifai_model=False,
        model_type_id="visual-classifier"
      )
      print(f"🔍 DEBUG: Found {len(models_data)} visual-classifier models")
      
      # Convert dict data to simple objects we can use
      class SimpleModel:
        def __init__(self, data):
          self.id = data.get('id')
          self.name = data.get('id')  # Use id as name if name not available
          self.user_id = data.get('user_id')
          self.app_id = data.get('app_id')
      
      community_visual_classifiers = [SimpleModel(m) for m in models_data]
      community_visual_classifiers_ids_only = [x.id for x in community_visual_classifiers]
      if len(community_visual_classifiers_ids_only) > 0:
        print(f"🔍 DEBUG: First few models: {community_visual_classifiers_ids_only[:5]}")
    except Exception as e:
      st.error(f"Error listing visual-classifier models: {e}")
      print(f"🔍 DEBUG: Exception details: {type(e).__name__}: {str(e)}")
      import traceback
      print(traceback.format_exc())
      community_visual_classifiers = []
      community_visual_classifiers_ids_only = []

    if len(community_visual_classifiers_ids_only) == 0:
      st.warning("No visual-classifier models found via API. Using fallback model.")
      st.info("💡 Tip: Verify your PAT has 'Predict on Public Models' scope at https://clarifai.com/settings/security")
      # Fallback to well-known model
      vis_class_model_id = "general-image-recognition"
      vis_class_model_name = "General Image Recognition"
      vis_class_user_id = "clarifai"
      vis_class_app_id = "main"
    else:
      default_index = min(10, len(community_visual_classifiers_ids_only) - 1)
      vis_class_model_id = st.selectbox(
        label = 'Select Image Classification',
        options = community_visual_classifiers_ids_only,
        index = default_index
      )

      selected_vis_clas_model = next((x for x in community_visual_classifiers if x.id == vis_class_model_id), community_visual_classifiers[0])
      vis_class_model_name = selected_vis_clas_model.name
      vis_class_user_id = selected_vis_clas_model.user_id
      vis_class_app_id = selected_vis_clas_model.app_id

    vis_class_max_concepts = st.slider(label = 'Specify max concepts', min_value = 1, max_value = 200, value = 12)

    # GenAI Selection
    try:
      print("🔍 DEBUG: Fetching multimodal-to-text models...")
      
      # Use User class to browse all community models
      user_client = User(pat=auth._pat)
      models_data = user_client.list_models(
        user_id="all",
        show=False,
        return_clarifai_model=False,
        model_type_id="multimodal-to-text"
      )
      print(f"🔍 DEBUG: Found {len(models_data)} multimodal-to-text models")
      
      # Convert dict data to simple objects we can use
      class SimpleModel:
        def __init__(self, data):
          self.id = data.get('id')
          self.name = data.get('id')  # Use id as name if name not available
          self.user_id = data.get('user_id')
          self.app_id = data.get('app_id')
      
      community_llvms = [SimpleModel(m) for m in models_data]
      community_llvms_ids_only = [x.id for x in community_llvms]
      if len(community_llvms_ids_only) > 0:
        print(f"🔍 DEBUG: First few models: {community_llvms_ids_only[:5]}")
    except Exception as e:
      st.error(f"Error listing multimodal-to-text models: {e}")
      print(f"🔍 DEBUG: Exception details: {type(e).__name__}: {str(e)}")
      import traceback
      print(traceback.format_exc())
      community_llvms = []
      community_llvms_ids_only = []

    if len(community_llvms_ids_only) == 0:
      st.warning("No multimodal-to-text models found via API. Using fallback model.")
      st.info("💡 Tip: Verify your PAT has 'Predict on Public Models' scope at https://clarifai.com/settings/security")
      # Fallback to well-known model
      llvm_model_id = "GPT-4"
      llvm_model_name = "GPT-4"
      llvm_user_id = "openai"
      llvm_app_id = "chat-completion"
    else:
      # Try to find mm-poly-8b, otherwise use default index
      try:
        llvm_default_index = community_llvms_ids_only.index("mm-poly-8b")
      except ValueError:
        llvm_default_index = min(10, len(community_llvms_ids_only) - 1)
      
      llvm_model_id = st.selectbox(
        label = 'Select GenAI Model',
        options = community_llvms_ids_only,
        index = llvm_default_index
      )

      selected_llvm = next((x for x in community_llvms if x.id == llvm_model_id), community_llvms[0])
      llvm_model_name = selected_llvm.name
      llvm_user_id = selected_llvm.user_id
      llvm_app_id = selected_llvm.app_id

    # llvm inference params
    llvm_temp = st.slider(label = 'Temperature', min_value = 0.0, max_value = 1.0, value = 0.8)
    llvm_max_tokens = st.number_input(label = 'Max Tokens', value = 512)
    llvm_top_p = st.slider(label = 'Top P', min_value = 0.0, max_value = 1.0, value = 0.8)

    technical_prompt = st.text_area(
      height = 150,
      label = 'Technical Prompt',
      value = 'Only respond to the following prompt in a json-formatted list of 10 individual concepts with confidence scores. Example format: [{"concept": "concept1", "confidence": 0.95}, {"concept": "concept2", "confidence": 0.87}, ...]. Return ONLY the JSON array, no other text.'
    )

    # Output Display options
    st.subheader('Output Display Options')

    tag_bg_color = st.color_picker(label = 'Tag Background Color', value = '#aabbcc')
    tag_text_color = st.color_picker(label = 'Tag Text Color', value = '#2B2D37')

  
  #### Snap and Search Options  
  with st.expander('Snap and Search'):

    sas_subheader_title = st.text_input(label = 'Snap&Search Subheader Text', value = '✨ Leveraging Clarifai for Snap & Search ✨')


  #### "Generative AI for Copy" Options
  with st.expander('Generative AI for Copy'):
    genai_subheader_title = st.text_input(label = 'GenAI Subheader Text', value = '✨ Leveraging Clarifai to Assist in Generating Copy ✨')
  
    genai_carousel_images = st.text_area(
      height = 300,
      label = 'Prepopulated Carousel Images.',
      help = "One URL per line. No quotations. Underlying code will take in the entire text box's value as a single string, then split using `theTextString.split('\n')`",
      value = 'https://s3.amazonaws.com/samples.clarifai.com/dam_demo_shirt_1.jpeg\nhttps://s3.amazonaws.com/samples.clarifai.com/dam_demo_shirt_2.jpeg\nhttps://s3.amazonaws.com/samples.clarifai.com/dam_demo_pants_1.jpeg\nhttps://s3.amazonaws.com/samples.clarifai.com/dam_demo_pants_2.jpeg',
    )

    genai_community_link = 'https://clarifai.com/explore/models?filterData=%5B%7B%22field%22%3A%22model_type_id%22%2C%22value%22%3A%5B%22multimodal-to-text%22%5D%7D%5D&page=1&perPage=24'
    genai_model_url = st.text_input(
      label = "Enter GenAI Model's Full URL",
      help = f"Specifically, a `multimodal-to-text` model, such as the ones found here: [Clarifai Community]({genai_community_link})",
      value = "https://clarifai.com/clarifai/main/models/mm-poly-8b"
    )
    
    # Inference parameters for Tab 3
    genai_temp = st.slider(label = 'Copy Generation Temperature', min_value = 0.0, max_value = 1.0, value = 0.7)
    genai_max_tokens = st.number_input(label = 'Copy Generation Max Tokens', value = 1024)
    genai_top_p = st.slider(label = 'Copy Generation Top P', min_value = 0.0, max_value = 1.0, value = 0.9)


####################
####  MAIN PAGE ####
####################

st.image(company_logo, width=company_logo_width)
st.title(page_title)

tab1, tab2, tab3 = st.tabs(['Digital Asset Management', 'Snap and Search', 'Generative AI for Copy'])


##############################
#### Content Organization ####
##############################

with tab1:
  st.subheader(dam_subheader_title)

  with st.form(key='input-data-url'):
    
    # url version
    upload_image_url = st.text_input(label = 'Enter image url:', value = dam_default_image)
    business_prompt_url = st.text_input(
      label = 'Enter prompt for GenAI Model',
      value = "Describe the following image, with a focus on stylistic qualities that a creative designer would consider when selecting an image"
    )
    submitted_url = st.form_submit_button("Upload")
  
  st.write('')

  t1_col1, t1_col2 = st.columns([1,2])
  
  with t1_col1:
    if submitted_url:
      st.image(upload_image_url)
      business_prompt = business_prompt_url

  with t1_col2:
    if submitted_url:

      #### Fast Classifiers
      st.subheader(f'Fast Classifiers:')

      with st.spinner():
        # with st.expander(label=f'{vis_class_model_name}'):

        color_model = Model(pat = auth._pat, model_id = 'color-recognition', user_id = 'clarifai', app_id = 'main')

        if submitted_url == True:
          color_pred = color_model.predict_by_url(url = upload_image_url, input_type = 'image')

          color_tuple_of_tuples = tuple([(f'{x.w3c.name}', f'{x.value*100:.3f}', x.w3c.hex, text_color_for_background(x.w3c.hex)) for x in color_pred.outputs[0].data.colors])

          list_with_empty_strings = []
          for item in color_tuple_of_tuples:
              list_with_empty_strings.append(item)
              list_with_empty_strings.append(" ")  # Add an empty string after each item

          # Remove the last empty string as it's not needed
          if list_with_empty_strings[-1] == "":
              list_with_empty_strings.pop()

          # Convert back to a tuple if needed
          color_tuple_of_tuples = tuple(list_with_empty_strings)

          st.write(f'Color Recognition Model')
          annotated_text(*color_tuple_of_tuples)

      st.write('')

      with st.spinner():
        if vis_class_model_id and vis_class_user_id and vis_class_app_id:
          try:
            vis_class_model = Model(
              pat = auth._pat,
              model_id = vis_class_model_id,
              user_id = vis_class_user_id,
              app_id = vis_class_app_id
            )

            if submitted_url == True:
              vis_class_pred = vis_class_model.predict_by_url(url = upload_image_url, input_type = 'image', inference_params = {'max_concepts': vis_class_max_concepts})
              vis_class_tuple_of_tuples = tuple([(f'{x.name}', f'{x.value:.3f}', tag_bg_color, tag_text_color) for x in vis_class_pred.outputs[0].data.concepts])

              list_with_empty_strings = []
              for item in vis_class_tuple_of_tuples:
                  list_with_empty_strings.append(item)
                  list_with_empty_strings.append(" ")  # Add an empty string after each item

              # Remove the last empty string as it's not needed
              if list_with_empty_strings[-1] == "":
                  list_with_empty_strings.pop()

              # Convert back to a tuple if needed
              vis_class_tuple_of_tuples = tuple(list_with_empty_strings)

              st.write('General Image Recognition')
              annotated_text(*vis_class_tuple_of_tuples)
          except Exception as e:
            error_msg = str(e)
            if "restricted to dedicated compute" in error_msg:
              st.error(f"Model '{vis_class_model_id}' requires dedicated compute (not available on shared infrastructure).")
              st.info("Please select a different model from the sidebar that supports shared compute.")
            else:
              st.error(f"Visual classifier prediction failed: {e}")
            print(f"🔍 DEBUG: Visual classifier error: {e}")
        else:
          st.info('No visual-classifier model available to run predictions.')

      st.write('')

      ### LLVM Output
      st.subheader(f'Generative AI:')
      with st.spinner():

        if llvm_model_id and llvm_user_id and llvm_app_id:
          try:
            llvm_class_model = Model(pat = auth._pat, model_id = llvm_model_id, user_id = llvm_user_id, app_id = llvm_app_id)
            llvm_inference_params = {'temperature': llvm_temp, 'max_tokens': llvm_max_tokens, 'top_p': llvm_top_p}

            if submitted_url == True:
              # Debug: Log the request details
              full_prompt = f'{technical_prompt}: {business_prompt}'
              print("\n" + "="*80)
              print("🔍 DEBUG: GenAI API Request")
              print("="*80)
              print(f"Model: {llvm_model_id}")
              print(f"User ID: {llvm_user_id}")
              print(f"App ID: {llvm_app_id}")
              print(f"Image URL: {upload_image_url}")
              print(f"Full Prompt:\n{full_prompt}")
              print(f"Inference Params: {llvm_inference_params}")
              print("="*80 + "\n")
              
              llvm_pred = llvm_class_model.predict(
                inputs = [Inputs.get_multimodal_input(input_id = '', image_url = upload_image_url, raw_text = full_prompt)],
                inference_params = llvm_inference_params
              )

              # Debug: Log the response
              print("\n" + "="*80)
              print("🔍 DEBUG: GenAI API Response")
              print("="*80)
              print(f"Response Status: {llvm_pred.status}")
              print(f"Number of outputs: {len(llvm_pred.outputs)}")
              if llvm_pred.outputs:
                print(f"Raw Output:\n{llvm_pred.outputs[0].data.text.raw}")
              print("="*80 + "\n")

              # wrangling output and cleaning up / converting to labels
              llvm_output = llvm_pred.outputs[0].data.text.raw

              ########################################
              #### <hardcoded debugging section>  ####
              ########################################

              # extra cleanup, in case instructions get ignored
              llvm_output = llvm_output.replace('json','').strip()
              llvm_output = llvm_output.replace('```','').strip()

              ########################################
              #### </hardcoded debugging section> ####
              ########################################

              # Parse the output - handle both old format (strings) and new format (objects)
              parsed_output = ast.literal_eval(llvm_output)
              if parsed_output and isinstance(parsed_output[0], dict):
                # New format with confidence: [{"concept": "name", "confidence": 0.95}, ...]
                llvm_tuple_of_tuples = tuple([
                  (item.get('concept', item.get('name', 'unknown')), f"{item.get('confidence', 0):.3f}", tag_bg_color, tag_text_color) 
                  for item in parsed_output
                ])
              else:
                # Old format (just strings): ["concept1", "concept2", ...]
                llvm_tuple_of_tuples = tuple([(x, '', tag_bg_color, tag_text_color) for x in parsed_output])
              
              list_with_empty_strings = []
              for item in llvm_tuple_of_tuples:
                  list_with_empty_strings.append(item)
                  list_with_empty_strings.append(" ")  # Add an empty string after each item

              # Remove the last empty string as it's not needed
              if list_with_empty_strings[-1] == "":
                  list_with_empty_strings.pop()

              # Convert back to a tuple if needed
              llvm_tuple_of_tuples = tuple(list_with_empty_strings)

              st.write(f'{llvm_model_id}')
              annotated_text(*llvm_tuple_of_tuples)
          except Exception as e:
            error_msg = str(e)
            if "restricted to dedicated compute" in error_msg:
              st.error(f"Model '{llvm_model_id}' requires dedicated compute (not available on shared infrastructure).")
              st.info("Please select a different model from the sidebar that supports shared compute.")
            else:
              st.error(f"GenAI prediction failed: {e}")
            print(f"🔍 DEBUG: GenAI prediction error: {e}")
        else:
          st.info('No multimodal-to-text model available to run GenAI.')


#########################
#### snap and search ####
#########################

MODEL_ID = "apparel-detection"
MODEL_VERSION_ID = "1ed35c3d176f45d69d2aa7971e6ab9fe"
end_results = None

with tab2:

  st.subheader(sas_subheader_title)

  with st.form(key='sas-input-data-url'):
    sas_upload_image_url = st.text_input(label = 'Enter image url:', value = dam_default_image)
    submitted = st.form_submit_button("Submit")

  t2_col1, t2_col2 = st.columns([1,2])
  with t2_col1:

    with st.form("CompleteForm"):

      # settings
      selected_color = 'blue'
      matches_to_show = 20
      line_thickness = 'Medium'
      confidence = 70
              
    if submitted:

      # Call Clarifai Apparel model
      output = call_apparel_model(sas_upload_image_url, confidence, selected_color, line_thickness, userDataObject=userDataObject, metadata=auth.metadata, stub=stub)

      # Visual Search
      end_results = call_visual_search(sas_upload_image_url, confidence, output, matches_to_show, stub, auth.metadata, userDataObject)

  # display results
  with t2_col2:
    if end_results:

      num_columns = 4

      for end_result in end_results:
        im_crop = end_result['im_crop']

        # results
        concept = end_result['concept'][:8]
        hits = end_result['hits'][:8]

        with st.expander(f'Detected item: {concept}', expanded=True):
          im_urls = [x.input.data.image.url for x in hits]
          metadata = [x.input.data.metadata for x in hits]
          metadata_dict = [MessageToDict(x) for x in metadata]

          for i in range(int(len(im_urls)/num_columns)):
            cols = st.columns(num_columns + 1)

            # insert cropped source image
            if i == 0:
              max_height = 300
              new_width = int(max_height * im_crop.width / im_crop.height)
              resized_image = im_crop.resize((new_width, max_height), Image.Resampling.LANCZOS)
              cols[0].image(resized_image, use_column_width=True)

            # insert rest of the images
            for col_idx in range(1, num_columns+1):
              try:
                cols[col_idx].image(im_urls[(i*num_columns)+col_idx-1])
                
              except IndexError:
                continue
    else:
      pass


######################
#### GenerativeAI ####
######################

with tab3:
  st.subheader(genai_subheader_title)

  with st.expander('Underlying Prompt', expanded=False):
    copy_prompt = st.text_input(label='prompt:', value='Write a product description for this item to be used on a retail/resellers website.', label_visibility='hidden')

  sample_images = genai_carousel_images.split('\n')
  img = image_select(label = "Select an image:",images = sample_images,)

  col1, col2 = st.columns([2,3])

  with col1:
    st.image(img)

  with col2:
    st.subheader('AI Generated Product Description')
    with st.spinner(text='Generating product description...'):
      try:
        # Debug: Log the request details
        genai_inference_params = {'temperature': genai_temp, 'max_tokens': genai_max_tokens, 'top_p': genai_top_p}
        print("\n" + "="*80)
        print("🔍 DEBUG: Tab 3 GenAI Copy API Request")
        print("="*80)
        print(f"Model URL: {genai_model_url}")
        print(f"Image URL: {img}")
        print(f"Prompt: {copy_prompt}")
        print(f"Inference Params: {genai_inference_params}")
        print("="*80 + "\n")
        
        model_prediction = Model(genai_model_url, pat=auth._pat).predict(
          inputs = [Inputs.get_multimodal_input(input_id="",image_url=img, raw_text=copy_prompt)],
          inference_params = genai_inference_params
        )
        
        # Debug: Log the response
        print("\n" + "="*80)
        print("🔍 DEBUG: Tab 3 GenAI Copy API Response")
        print("="*80)
        print(f"Response Status: {model_prediction.status}")
        print(f"Number of outputs: {len(model_prediction.outputs)}")
        if model_prediction.outputs:
          print(f"Raw Output:\n{model_prediction.outputs[0].data.text.raw}")
        print("="*80 + "\n")
        
        st.markdown(model_prediction.outputs[0].data.text.raw)
      except Exception as e:
        st.error(f"GenAI model call failed: {e}")
        st.info("Verify the model URL is correct and accessible in your Clarifai account.")
        print(f"🔍 DEBUG: Tab 3 GenAI error: {e}")


####################
####  FOOTER    ####
####################

footer(st)