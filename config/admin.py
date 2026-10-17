from django.contrib.admin import AdminSite


class PetDonationAdminSite(AdminSite):
    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request, app_label)
        if app_label:
            return app_list

        donation_app = next((app for app in app_list if app["app_label"] == "donation"), None)
        auth_app = next((app for app in app_list if app["app_label"] == "auth"), None)
        if not donation_app or not auth_app:
            return app_list

        user_models = [model for model in donation_app["models"] if model["object_name"] == "User"]
        if user_models:
            donation_app["models"] = [model for model in donation_app["models"] if model["object_name"] != "User"]
            auth_app["models"].extend(user_models)
            auth_app["models"].sort(key=lambda model: model["name"].lower())
        return [app for app in app_list if app["models"]]
