from Kultiva.models import User

# 1. Grab your newly created admin account
my_admin = User.objects.get(username='admin')

# 2. Force the verification to True
my_admin.is_verified = True

# 3. Explicitly set the role to ADMIN (just to be safe)
my_admin.role = 'ADMIN'

# 4. Save the changes to the database
my_admin.save()

# 5. Exit the shell
exit()