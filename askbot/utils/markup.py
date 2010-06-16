from askbot import const

def format_mention_in_html(mentioned_user):
    url = mentioned_user.get_profile_url()
    username = mentioned_user.username
    return '<a href="%s">@%s</a>' % (url, username)

def extract_first_matching_mentioned_author(text, anticipated_authors):

    if len(text) == 0:
        return None, ''

    for a in anticipated_authors:
        if text.startswith(a.username):
            ulen = len(a.username)
            if len(text) == ulen:
                text = ''
            elif text[ulen] in const.TWITTER_STYLE_MENTION_TERMINATION_CHARS:
                text = text[ulen:]
            else:
                #near miss, here we could insert a warning that perhaps
                #a termination character is needed
                continue
            return a, text
    return None, text

def extract_mentioned_name_seeds(text):
    extra_name_seeds = set()
    while '@' in text:
        pos = text.index('@')
        text = text[pos+1:]#chop off prefix
        name_seed = ''
        for c in text:
            if c in const.TWITTER_STYLE_MENTION_TERMINATION_CHARS:
                extra_name_seeds.add(name_seed)
                name_seed = ''
                break
            if len(name_seed) > 10:
                extra_name_seeds.add(name_seed)
                name_seed = ''
                break
            if c == '@':
                if len(name_seed) > 0:
                    extra_name_seeds.add(name_seed)
                    name_seed = ''
                break
            name_seed += c
        if len(name_seed) > 0:
            #in case we run off the end of text
            extra_name_seeds.add(name_seed)

    return extra_name_seeds

def mentionize_text(text, anticipated_authors):
    output = ''
    mentioned_authors = list()
    while '@' in text:
        #the purpose of this loop is to convert any occurance of 
        #'@mention ' syntax
        #to user account links leading space is required unless @ is the first
        #character in whole text, also, either a punctuation or 
        #a ' ' char is required after the name
        pos = text.index('@')

        #save stuff before @mention to the output
        output += text[:pos]#this works for pos == 0 too

        if len(text) == pos + 1:
            #finish up if the found @ is the last symbol
            output += '@'
            text = ''
            break

        if pos > 0:

            if text[pos-1] in const.TWITTER_STYLE_MENTION_TERMINATION_CHARS:
                #if there is a termination character before @mention
                #indeed try to find a matching person
                text = text[pos+1:]
                mentioned_author, text = \
                                    extract_first_matching_mentioned_author(
                                                            text, 
                                                            anticipated_authors
                                                        )
                if mentioned_author:
                    mentioned_authors.append(mentioned_author)
                    output += format_mention_in_html(mentioned_author)
                else:
                    output += '@'

            else:
                #if there isn't, i.e. text goes like something@mention,
                #do not look up people
                output += '@'
                text = text[pos+1:]
        else:
            #do this if @ is the first character
            text = text[1:]
            mentioned_author, text = \
                                extract_first_matching_mentioned_author(
                                                    text, 
                                                    anticipated_authors
                                                )
            if mentioned_author:
                mentioned_authors.append(mentioned_author)
                output += format_mention_in_html(mentioned_author)
            else:
                output += '@'

    #append the rest of text that did not have @ symbols
    output += text
    return mentioned_authors, output
