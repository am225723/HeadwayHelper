import re

with open("frontend/src/app/page.tsx", "r") as f:
    content = f.read()

# Add Provider features to the bottom of the Generation Form area or Patient detail
provider_features_html = """
        <Card className="mt-5 border-moss/20 bg-gradient-to-br from-white to-sage/60">
          <SectionHeader title="Favorite / Quick-Access Templates" subtitle="Coming soon: Star your most frequently used templates for quicker access." />
        </Card>
        <Card className="mt-5 border-moss/20 bg-gradient-to-br from-white to-sage/60">
          <SectionHeader title="Real-Time Generation Progress Indicator" subtitle="Coming soon: Detailed progress bar while waiting for AI generation." />
        </Card>
        <Card className="mt-5 border-moss/20 bg-gradient-to-br from-white to-sage/60">
          <SectionHeader title="Quick Edit Inline Mode" subtitle="Coming soon: Inline editing mode for minor adjustments before saving." />
        </Card>
        <Card className="mt-5 border-moss/20 bg-gradient-to-br from-white to-sage/60">
          <SectionHeader title="Automated Follow-Up Task Extraction" subtitle="Coming soon: Automatically extract action items into a to-do list." />
        </Card>
"""

content = content.replace("          {currentUser?.role === \"ADMIN\" && adminConfig && token ? <AdminSettingsPanel config={adminConfig} token={token} diagnostics={diagnostics} onConfig={setAdminConfig} onDiagnostics={setDiagnostics} /> : null}\n        </section>", "          {currentUser?.role === \"ADMIN\" && adminConfig && token ? <AdminSettingsPanel config={adminConfig} token={token} diagnostics={diagnostics} onConfig={setAdminConfig} onDiagnostics={setDiagnostics} /> : null}\n" + provider_features_html + "\n        </section>")

with open("frontend/src/app/page.tsx", "w") as f:
    f.write(content)
