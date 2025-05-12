import streamlit as st
import numpy as np
from PIL import Image
import io
import zipfile
import base64
import time
from io import BytesIO
import os
import math
from sss_core import split_secret, recover_secret
from image_utils import (
    image_to_shares, 
    shares_to_image, 
    create_preview_image, 
    download_button
)

# Set page configuration
st.set_page_config(
    page_title="Shamir's Secret Sharing Image Tool",
    page_icon="🔐",
    layout="wide",
)

# Custom CSS for styling
st.markdown("""
<style>
    .main {
        background-color: #edf2f4;
    }
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    h1, h2, h3 {
        color: #2b2d42;
    }
    .stButton button {
        background-color: #d90429;
        color: white;
        border-radius: 5px;
        border: none;
        padding: 0.5rem 1rem;
        transition: background-color 0.3s;
    }
    .stButton button:hover {
        background-color: #ef233c;
    }
    .info-box {
        background-color: #8d99ae;
        color: white;
        padding: 1rem;
        border-radius: 5px;
        margin-bottom: 1rem;
    }
    .success-box {
        background-color: #2b2d42;
        color: white;
        padding: 1rem;
        border-radius: 5px;
        margin-bottom: 1rem;
    }
    .error-box {
        background-color: #ef233c;
        color: white;
        padding: 1rem;
        border-radius: 5px;
        margin-bottom: 1rem;
    }
    /* For image previews */
    .share-preview {
        border: 2px solid #8d99ae;
        border-radius: 5px;
        padding: 5px;
        margin: 5px;
    }
    /* For tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #8d99ae;
        border-radius: 4px 4px 0px 0px;
        color: white;
        padding: 10px 20px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #2b2d42 !important;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state variables if they don't exist
if 'shares' not in st.session_state:
    st.session_state.shares = None
if 'original_image' not in st.session_state:
    st.session_state.original_image = None
if 'share_previews' not in st.session_state:
    st.session_state.share_previews = []
if 'combined_image' not in st.session_state:
    st.session_state.combined_image = None
if 'selected_shares' not in st.session_state:
    st.session_state.selected_shares = []
if 'uploaded_share_data' not in st.session_state:
    st.session_state.uploaded_share_data = []
if 'threshold' not in st.session_state:
    st.session_state.threshold = 2

# Header
st.title("🔐 Shamir's Secret Sharing Image Tool")
st.markdown("""
<div class="info-box">
This application is designed to encrypt and split images using the Shamir's Secret Sharing algorithm, and to reconstruct the original image from the shares.
</div>
""", unsafe_allow_html=True)

# Create tabs for split and combine operations
tab1, tab2 = st.tabs(["📊 Split Image (Encrypt)", "🔄 Combine Shares (Decrypt)"])

with tab1:
    st.header("Split Image")
    
    # Image upload
    uploaded_file = st.file_uploader("Upload an image (JPG, PNG)", type=["jpg", "jpeg", "png"])
    
    if uploaded_file is not None:
        try:
            # Display image preview
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded Image", use_container_width=True)
            st.session_state.original_image = image
            
            # Show a warning for large images
            if image.width * image.height > 500000:  # Roughly a 700x700 image
                st.markdown("""
                <div class="error-box">
                You have uploaded a large image! Processing may take a while. Consider using a smaller image for faster results.
                </div>
                """, unsafe_allow_html=True)
            
            # Input parameters
            col1, col2 = st.columns(2)
            with col1:
                k = st.number_input("Total Number of Shares (k)", min_value=2, max_value=10, value=3, step=1)
            with col2:
                t = st.number_input("Minimum Required Shares (t)", min_value=2, max_value=k, value=min(2, k), step=1)
                st.session_state.threshold = t
            
            # Parameter validation
            if t > k:
                st.markdown("""
                <div class="error-box">
                Error: Threshold (t) cannot be greater than the total number of shares (k)!
                </div>
                """, unsafe_allow_html=True)
            else:
                # Process button
                if st.button("Encrypt and Create Shares"):
                    with st.spinner("Processing image and generating shares..."):
                        progress_bar = st.progress(0)
                        
                        # Process the image and create shares
                        try:
                            shares, share_previews = image_to_shares(
                                image, k, t, 
                                progress_callback=lambda p: progress_bar.progress(p)
                            )
                            
                            st.session_state.shares = shares
                            st.session_state.share_previews = share_previews
                            
                            progress_bar.progress(1.0)
                            time.sleep(0.5)  # Give a moment to see 100%
                            
                            st.markdown("""
                            <div class="success-box">
                            Success! Shares have been generated.
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Display share previews in a grid
                            st.subheader("Generated Shares")
                            
                            # Create columns for previews - ensure we have at least 1 column
                            num_cols = min(3, k)
                            if num_cols <= 0:
                                num_cols = 1
                            cols = st.columns(num_cols)  # Maximum 3 columns
                            for i, (share_img, share_data) in enumerate(zip(share_previews, shares)):
                                col_idx = i % len(cols)
                                with cols[col_idx]:
                                    st.image(share_img, caption=f"Share {i+1}", use_container_width=True)
                                    
                                    # Download button for individual share
                                    img_byte_arr = io.BytesIO()
                                    share_img.save(img_byte_arr, format='PNG')
                                    img_byte_arr = img_byte_arr.getvalue()
                                    
                                    download_btn = download_button(
                                        img_byte_arr,
                                        f"share_{i+1}.png",
                                        f"Download Share {i+1} (.png)"
                                    )
                                    st.markdown(download_btn, unsafe_allow_html=True)
                            
                            # Create ZIP with all shares
                            zip_buffer = BytesIO()
                            with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                                for i, (share_img, _) in enumerate(zip(share_previews, shares)):
                                    img_byte_arr = BytesIO()
                                    share_img.save(img_byte_arr, format='PNG')
                                    img_byte_arr.seek(0)
                                    zip_file.writestr(f"share_{i+1}.png", img_byte_arr.read())
                            
                            # Download button for ZIP file
                            st.markdown("### Download All Shares")
                            zip_button = download_button(
                                zip_buffer.getvalue(),
                                "all_shares.zip",
                                "Download All Shares (.zip)"
                            )
                            st.markdown(zip_button, unsafe_allow_html=True)
                            
                        except Exception as e:
                            st.markdown(f"""
                            <div class="error-box">
                            Error: An issue occurred while generating shares: {str(e)}
                            </div>
                            """, unsafe_allow_html=True)
        
        except Exception as e:
            st.markdown(f"""
            <div class="error-box">
            Error: An issue occurred while uploading the image: {str(e)}
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Please upload an image file. (JPG or PNG format)")

with tab2:
    st.header("Combine Shares")
    
    # Share upload
    st.markdown("""
    <div class="info-box">
    To combine the image, you need to upload at least the threshold number (t) of shares. 
    Share filenames should be in the format 'share_X.png', where X is the share number.
    </div>
    """, unsafe_allow_html=True)
    
    uploaded_shares = st.file_uploader(
        f"Upload Shares (At least {st.session_state.threshold})", 
        type=["png"], 
        accept_multiple_files=True
    )
    
    if uploaded_shares:
        try:
            # Clear previous uploads if new ones are added
            if len(uploaded_shares) != len(st.session_state.uploaded_share_data):
                st.session_state.uploaded_share_data = []
            
            # Process uploaded shares
            if not st.session_state.uploaded_share_data:
                for share_file in uploaded_shares:
                    try:
                        # Extract share index from filename: "share_X.png" or "share_X (Y).png"
                        filename = share_file.name
                        if filename.startswith("share_") and filename.endswith(".png"):
                            import re
                            match = re.search(r'share_(\d+)', filename)
                            if match:
                                idx = int(match.group(1))
                            else:
                                idx = len(st.session_state.uploaded_share_data) + 1  # Fallback
                        else:
                            idx = len(st.session_state.uploaded_share_data) + 1  # Fallback
                        
                        share_img = Image.open(share_file)
                        st.session_state.uploaded_share_data.append((idx, share_img))
                    except Exception as e:
                        st.markdown(f"""
                        <div class="error-box">
                        Error loading share: {filename} - {str(e)}
                        </div>
                        """, unsafe_allow_html=True)
            
            # Display uploaded shares
            st.subheader("Uploaded Shares")
            num_cols = min(3, len(st.session_state.uploaded_share_data))
            if num_cols <= 0:
                num_cols = 1
            cols = st.columns(num_cols)
            
            for i, (idx, share_img) in enumerate(st.session_state.uploaded_share_data):
                col_idx = i % len(cols)
                with cols[col_idx]:
                    st.image(share_img, caption=f"Share {idx}", use_container_width=True)
            
            # Check if enough shares are uploaded
            if len(st.session_state.uploaded_share_data) < 2:
                st.markdown(f"""
                <div class="error-box">
                You need to upload at least 2 shares to combine the image. You have uploaded {len(st.session_state.uploaded_share_data)}.
                </div>
                """, unsafe_allow_html=True)
            else:
                # Combine button
                if st.button("Combine and Show Image"):
                    with st.spinner("Combining shares..."):
                        progress_bar = st.progress(0)
                        
                        try:
                            # Actually combine the shares to recover the original image
                            combined_image = shares_to_image(
                                st.session_state.uploaded_share_data,
                                progress_callback=lambda p: progress_bar.progress(p)
                            )
                            
                            st.session_state.combined_image = combined_image
                            progress_bar.progress(1.0)
                            time.sleep(0.5)  # Give a moment to see 100%
                            
                            st.markdown("""
                            <div class="success-box">
                            Combine successful! Original image has been reconstructed.
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # Display the recovered image
                            st.subheader("Reconstructed Original Image")
                            st.image(combined_image, caption="Reconstructed Image", use_container_width=True)
                            
                            # Download button for the combined image
                            img_byte_arr = io.BytesIO()
                            combined_image.save(img_byte_arr, format='PNG')
                            img_byte_arr = img_byte_arr.getvalue()
                            
                            download_btn = download_button(
                                img_byte_arr,
                                "recovered_image.png",
                                "Download Original Image (.png)"
                            )
                            st.markdown(download_btn, unsafe_allow_html=True)
                            
                        except Exception as e:
                            st.markdown(f"""
                            <div class="error-box">
                            Error: An issue occurred while combining shares: {str(e)}
                            </div>
                            """, unsafe_allow_html=True)
        
        except Exception as e:
            st.markdown(f"""
            <div class="error-box">
            Error: An issue occurred while processing shares: {str(e)}
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Please upload the image shares you want to combine.")

# Footer
st.markdown("""
---
<p style="text-align: center; color: #8d99ae;">
Shamir's Secret Sharing Image Encryption/Decryption App © 2025
</p>
""", unsafe_allow_html=True)
