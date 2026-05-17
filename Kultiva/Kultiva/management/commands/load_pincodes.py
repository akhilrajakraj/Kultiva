import csv
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from Kultiva.models import PincodeDirectory 

class Command(BaseCommand):
    help = 'Smart ingestion of raw Indian Postal CSV data into the PincodeDirectory table'

    def handle(self, *args, **kwargs):
        # 1. Look for the CSV in the data folder next to manage.py
        csv_path = os.path.join(settings.BASE_DIR, 'data', 'pincode.csv')
        
        if not os.path.exists(csv_path):
            self.stdout.write(self.style.ERROR(f"Critical Error: Could not find CSV at {csv_path}"))
            return

        self.stdout.write(self.style.WARNING("System Initialized: Opening Smart Data Filter Pipeline..."))

        seen_pincodes = set()
        locations_to_create = []
        batch_size = 5000 
        total_saved = 0

        # 2. Open the file and process the data
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row in reader:
                pincode_val = str(row.get('pincode', '')).strip()
                district_val = str(row.get('district', '')).strip().title() 
                state_val = str(row.get('statename', '')).strip().title()   

                # Skip empty rows or duplicate pincodes
                if not pincode_val or pincode_val in seen_pincodes:
                    continue
                
                seen_pincodes.add(pincode_val)

                # Pack into the standalone PincodeDirectory model
                locations_to_create.append(
                    PincodeDirectory(
                        pincode=pincode_val,
                        district=district_val,
                        state=state_val
                    )
                )

                # 3. Save to database in massive batches of 5000
                if len(locations_to_create) >= batch_size:
                    PincodeDirectory.objects.bulk_create(locations_to_create, ignore_conflicts=True)
                    total_saved += len(locations_to_create)
                    self.stdout.write(f"Safely loaded {total_saved} unique locations...")
                    locations_to_create = [] # Empty the batch box

            # 4. Save any leftovers at the very end
            if locations_to_create:
                PincodeDirectory.objects.bulk_create(locations_to_create, ignore_conflicts=True)
                total_saved += len(locations_to_create)

        self.stdout.write(self.style.SUCCESS(f"Data Ingestion Complete! Safely locked {total_saved} pincodes into the Directory."))