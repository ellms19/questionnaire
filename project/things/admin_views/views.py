import json

from django.contrib.sites.shortcuts import get_current_site
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.contrib.auth.views import (
    LoginView as BaseLoginView, LogoutView as BaseLogoutView)
from django.core.exceptions import ValidationError
from django.db.models import Avg
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy, reverse
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_text
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.views.generic.edit import CreateView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.views.generic.base import TemplateView, RedirectView

from things.admin_forms.forms import (
    UserCreateForm, UserAuthForm, TestCreateForm,
)
from things.models import TestInfo, Question, Option, User, Student, TestResult
from things.utils.tasks import send_mail_wrapper
from things.utils.activation_token import activation_token


class RegistrationView(CreateView):
    form_class = UserCreateForm
    template_name = 'admin/registration.html'

    def form_valid(self, form):
        # noinspection PyAttributeOutsideInit
        self.object = form.save()
        context = {
            'domain': get_current_site(self.request),
            'uidb64': urlsafe_base64_encode(force_bytes(self.object.pk)),
            'token': activation_token.make_token(self.object),
        }
        html_message = render_to_string('admin/email_activation.html', context)
        send_mail_wrapper('Welcome to Questionnaire System! Confirm your email', '',
                          self.object.email, html_message)
        return HttpResponseRedirect(self.get_success_url())

    def form_invalid(self, form):
        return super(RegistrationView, self).form_invalid(form)

    def get_success_url(self):
        return reverse_lazy('admin-pre-activation')


class PreActivationView(TemplateView):
    template_name = 'admin/pre_activation.html'


class ActivationView(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        user_id = force_text(urlsafe_base64_decode(kwargs['uidb64']))
        return reverse_lazy('admin-tests', kwargs={'id': user_id})

    def get(self, request, *args, **kwargs):
        user = None
        try:
            user_id = force_text(urlsafe_base64_decode(kwargs['uidb64']))
            user = User.objects.get(id=user_id)
            correct = True
        except (TypeError, ValueError, OverflowError, User.DoesNotExist, ValidationError):
            correct = False

        if correct and activation_token.check_token(user, kwargs['token']):
            user.is_email_confirmed = True
            user.save()
            login(request, user)
            return super().get(request, *args, **kwargs)
        else:
            messages.error(self.request, 'Confirmation link is invalid')
            return HttpResponseRedirect(reverse_lazy('admin-login'))


class LoginView(BaseLoginView):
    form_class = UserAuthForm
    template_name = 'admin/login.html'

    def get_success_url(self):
        return reverse_lazy('admin-tests', kwargs={'id': self.request.user.id})


class LogoutView(BaseLogoutView):
    def get_next_page(self):
        return reverse_lazy('admin-login')


class BaseAdminView(LoginRequiredMixin):
    pass


class AdminTestCreateView(BaseAdminView, CreateView):
    model = TestInfo
    form_class = TestCreateForm
    template_name = 'admin/test_create.html'

    def form_valid(self, form):
        # noinspection PyAttributeOutsideInit
        self.object = form.save(commit=False)
        self.object.author = self.request.user
        self.object.save()
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('admin-test', kwargs={'user_id': self.request.user.id,
                                             'test_id': self.object.id})


class AdminTestListView(BaseAdminView, ListView):
    model = TestInfo
    context_object_name = 'tests'
    template_name = 'admin/tests.html'

    def get_queryset(self):
        return self.request.user.tests \
            .annotate(average_points=Avg('results__grade'))


class AdminTestDetailView(BaseAdminView, DetailView):
    model = TestInfo
    context_object_name = 'test'
    pk_url_kwarg = 'test_id'
    template_name = 'admin/test.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['average_points'] = self.get_object().results.aggregate(Avg('grade')).get('grade__avg')
        sql = 'SELECT "things_student"."id", "things_student"."first_name", ' \
              '"things_student"."last_name", "things_student"."speciality", ' \
              '"things_testresult"."grade", "things_testresult"."id" AS result_id ' \
              'FROM "things_student" ' \
              'INNER JOIN "things_testinfo_students"' \
              ' ON ("things_student"."id" = "things_testinfo_students"."student_id") ' \
              'LEFT JOIN "things_testresult" ' \
              'ON "things_student"."id"="things_testresult"."student_id" ' \
              'WHERE "things_testinfo_students"."testinfo_id" = %d ' \
              'ORDER BY "things_student"."first_name", "things_student"."last_name"' % self.object.pk
        context['students'] = Student.objects.raw(sql)
        return context

    def get_queryset(self):
        return self.request.user.tests.all()


class StudentResultDetailView(BaseAdminView, DetailView):
    model = TestResult
    context_object_name = 'result'
    pk_url_kwarg = 'result_id'
    template_name = 'admin/student_result.html'

    def get_queryset(self):
        test = get_object_or_404(TestInfo, author=self.request.user,
                                 id=self.kwargs['test_id'])
        return test.results.all()


@login_required
def admin_questions_create(request, user_id, test_id):
    test = get_object_or_404(TestInfo, id=test_id, author=request.user)
    if request.is_ajax() and request.method == 'POST':
        questions = json.loads(request.body.decode('utf-8'))
        errors = []
        single_choice_options_min = 2
        single_choice_options_max = 6
        single_choice_options_correct_max = 1
        multiple_choice_options_min = 3
        multiple_choice_options_max = 8
        multiple_choice_options_correct_min = 2

        if not len(questions) > 0:
            errors.append(
                {
                    'error': 'Test does not have any questions'
                }
            )

        for index in range(0, len(questions)):
            question = questions[index]
            options_len = len(question['options'])

            if not options_len > 0:
                errors.append(
                    {
                        'error': 'Question does not have any options',
                        'question': index,
                    }
                )
                continue

            if question['is_multiple_choice']:
                if options_len < multiple_choice_options_min:
                    errors.append({
                        'error': 'Multiple choice question should have at least {} options'.
                            format(multiple_choice_options_min),
                        'question': index,
                    })
                    continue
                elif options_len > multiple_choice_options_max:
                    errors.append({
                        'error': 'Multiple choice question can\'t have more than {} options'.
                            format(multiple_choice_options_max),
                        'question': index,
                    })
                    continue
            else:
                if options_len < single_choice_options_min:
                    errors.append({
                        'error': 'Single choice question should have at least {} options'.
                            format(single_choice_options_min),
                        'question': index,
                    })
                    continue
                elif options_len > single_choice_options_max:
                    errors.append({
                        'error': 'Single choice question can\'t have more than {} options'.
                            format(single_choice_options_max),
                        'question': index,
                    })
                    continue

            correct_options = 0
            for option in question['options']:
                if option['is_correct']:
                    correct_options += 1

            if question['is_multiple_choice']:
                if correct_options < multiple_choice_options_correct_min:
                    errors.append({
                        'error': 'Multiple choice question should have at least {} correct options'.
                            format(multiple_choice_options_correct_min),
                        'question': index,
                    })
                    continue
            else:
                if correct_options == 0:
                    errors.append({
                        'error': 'Single choice question should have {} correct option'.
                            format(single_choice_options_correct_max),
                        'question': index,
                    })
                    continue
                if correct_options > single_choice_options_correct_max:
                    errors.append({
                        'error': 'Single choice question can\'t have more than {} correct option'.
                            format(single_choice_options_correct_max),
                        'question': index,
                    })
                    continue

        if len(errors) > 0:
            return JsonResponse({'response': json.dumps(errors)}, status=400)
        else:
            for obj in questions:
                question = Question.objects.create(test=test,
                                                   question=obj['question'],
                                                   is_multiple_choice=obj['is_multiple_choice'])
                question.save()
                for opt in obj['options']:
                    option = Option.objects.create(question=question,
                                                   option=opt['option'],
                                                   is_correct=opt['is_correct'])
                    option.save()
        return JsonResponse({'response': "Questions were successfully created"}, status=200)

    return render(request, 'admin/question_populate.html', {'test': test})


@login_required
def admin_test(request, user_id, test_id):
    test = get_object_or_404(TestInfo, id=test_id, author=request.user)

    if test.questions.count() == 0:
        question = Question.objects.create(test=test, question='Enter the question', is_multiple_choice=False)
        Option.objects.create(question=question, option='Option 1', is_correct=False)
        Option.objects.create(question=question, option='Option 2', is_correct=False)

    return render(request, 'admin/question_create.html', {'test': test, 'questions': test.questions.all()})


@login_required
def admin_question_add(request, user_id, test_id):
    test = get_object_or_404(TestInfo, id=test_id, author=request.user)

    if request.is_ajax() and request.method == 'POST':
        question = Question.objects.create(test=test, question='Enter the question', is_multiple_choice=False)
        option_1 = Option.objects.create(question=question, option='Option 1', is_correct=False)
        option_2 = Option.objects.create(question=question, option='Option 2', is_correct=False)
        return JsonResponse(json.dumps({
            'id': question.id,
            'question': question.question,
            'options': [
                {
                    'id': option_1.id,
                    'option': option_1.option,
                    'is_correct': option_1.is_correct,
                },
                {
                    'id': option_2.id,
                    'option': option_2.option,
                    'is_correct': option_2.is_correct,
                }
            ]
        }),
            safe=False,
            status=200)

    return JsonResponse({'error': 'ajax request is required'}, status=400)


@login_required
def admin_question_update(request, user_id, test_id, question_id):
    if request.is_ajax() and request.method == 'POST':
        data = json.loads(request.body.decode('utf-8'))
        question = Question.objects.get(id=data['id'])
        question_changed = False
        if question.question != data['question']:
            question.question = data['question']
            question_changed = True

        correct_count = 0
        for opt in data['options']:
            option = Option.objects.get(id=opt['id'])
            changed = False
            if option.option != opt['option']:
                option.option = opt['option']
                changed = True

            if option.is_correct != opt['is_correct']:
                option.is_correct = opt['is_correct']
                changed = True

            if opt['is_correct']:
                correct_count += 1

            if changed:
                option.save()
        print(correct_count)
        if not question.is_multiple_choice and correct_count > 1:
            question.is_multiple_choice = True
            question_changed = True

        if question.is_multiple_choice and correct_count < 2:
            question.is_multiple_choice = False
            question_changed = True

        if question_changed:
            question.save()

        question.save()

        return JsonResponse({'response': 'Question was successfully saved'}, status=200)

    return JsonResponse({'error': 'ajax request is required'}, status=400)


@login_required
def admin_option_add(request, user_id, test_id, question_id):
    if request.is_ajax() and request.method == 'POST':
        question = get_object_or_404(Question, id=question_id)
        option = Option.objects.create(
            question=question,
            option='Option {}'.format(question.options.count() + 1),
            is_correct=False
        )
        return JsonResponse(json.dumps({'id': option.id,
                                        'question_id': question.id,
                                        'option': option.option,
                                        'is_correct': option.is_correct,
                                        }),
                            safe=False,
                            status=200)

    return JsonResponse({'error': 'ajax request is required'}, status=400)
