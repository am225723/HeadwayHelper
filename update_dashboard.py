import re

with open("frontend/src/app/page.tsx", "r") as f:
    content = f.read()

# Add Admin features
admin_features_html = """
        <Card className="mt-5 border-moss/20 bg-gradient-to-br from-white to-sage/60">
          <SectionHeader title="Custom Cleanup Rules Configurator" subtitle="Coming soon: UI to toggle and manage template rendering rules." />
        </Card>
        <Card className="mt-5 border-moss/20 bg-gradient-to-br from-white to-sage/60">
          <SectionHeader title="A/B Testing for AI Prompts" subtitle="Coming soon: Test different prompt structures within templates to optimize AI outputs." />
        </Card>
        <Card className="mt-5 border-moss/20 bg-gradient-to-br from-white to-sage/60">
          <SectionHeader title="Dark Mode Toggle" subtitle="Coming soon: Offer a dark mode option for the admin interface for better readability." />
        </Card>
"""

content = content.replace("      <div className=\"grid min-w-0 gap-5 2xl:grid-cols-2\">", admin_features_html + "\n      <div className=\"grid min-w-0 gap-5 2xl:grid-cols-2\">")


with open("frontend/src/app/page.tsx", "w") as f:
    f.write(content)
