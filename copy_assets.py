import shutil
import os

src_building = "/home/nyorii/.gemini/antigravity/brain/ada9cadf-287d-4d6a-ba62-fe40900a4cec/luxury_hostel_building_1785006771350.jpg"
src_tenant = "/home/nyorii/.gemini/antigravity/brain/ada9cadf-287d-4d6a-ba62-fe40900a4cec/tenant_avatar_1_1785006793926.jpg"

dest_dir = "/home/nyorii/Projects/rental-os/frontend/public"
os.makedirs(dest_dir, exist_ok=True)

if os.path.exists(src_building):
    shutil.copy(src_building, os.path.join(dest_dir, "building_bg.jpg"))
    print("[+] Copied building_bg.jpg")

if os.path.exists(src_tenant):
    shutil.copy(src_tenant, os.path.join(dest_dir, "tenant_avatar.jpg"))
    print("[+] Copied tenant_avatar.jpg")
