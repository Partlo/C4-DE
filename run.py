from c4de.core import C4DE_Bot
from local_token import TOKEN

try:
    client = C4DE_Bot()
    client.run(TOKEN)
except KeyboardInterrupt:
    pass
