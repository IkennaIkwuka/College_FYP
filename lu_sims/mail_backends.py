import email.policy

from django.core.mail.backends.console import EmailBackend as ConsoleEmailBackend


class ReadableConsoleEmailBackend(ConsoleEmailBackend):
    """Same as Django's console backend, except the printed message isn't
    soft-wrapped at 76 characters.

    Django's default policy (email.policy.default) wraps long lines for RFC 5322
    wire-format correctness - fine for real SMTP transport, where a mail client
    decodes the wrapping invisibly, but it splits any link over ~76 characters
    (e.g. the tokenized forgot-password/staff-setup links) across two lines with
    a trailing "=", which breaks the link if a developer copies it straight out
    of this console output by hand. Local-dev-only concern: production traffic
    goes through the SMTP backend instead, unaffected by this override.
    """

    def write_message(self, message):
        msg = message.message(policy=email.policy.default.clone(max_line_length=998))
        msg_data = msg.as_bytes()
        charset = msg.get_charset().get_output_charset() if msg.get_charset() else "utf-8"
        msg_data = msg_data.decode(charset)
        self.stream.write("%s\n" % msg_data)
        self.stream.write("-" * 79)
        self.stream.write("\n")
