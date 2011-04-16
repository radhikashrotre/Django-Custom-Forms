from django.shortcuts import redirect, render_to_response, HttpResponse
from django.http import Http404,HttpResponseRedirect
from django.template import RequestContext
from django.db import connection
from forms import CustomForm
from django.utils import simplejson as json
from customforms.models import *
from customforms.useful import *
from customforms.backups import *


def landing(request):
	return render_to_response('index.html',{})

def isRequired(text):
	#Checks whether a question is required or not
	
	if(text[len(text)-1])=='*':
		return'Y'
	else: 
		return 'N'

def onSubmit(request):
	#Stores the form structure in the database
	
	if request.is_ajax():
		if request.method == 'POST':
			elems=json.loads(request.raw_post_data)	
	
		form=Form.objects.create(title=elems['title'])

	for elem in elems['types']:
		question=Question.objects.create(form=form,question=elem['question'],ques_type=elem['typ'],required=isRequired(elem['question']))
		if elem['typ']=='radio':
			options=elem['opts'].split(',')
			for i in options:
				if i!='':
					Option.objects.create(question=question,opt=i,form=form)
	
	#Generating the dynamic model and creating the table
	dyn_model=dynamic_model(int(form.id))
	run_sql(dyn_model)
	
	return HttpResponse('OK')
	
def formList(request):
	#Lists all created forms
	
	return render_to_response('list.html',{'forms':Form.objects.order_by('-id')})	
	
def clearTables(request):
	#Clears all database tables
	
	Responses.objects.all().delete()
	Option.objects.all().delete()
	Question.objects.all().delete()
	Form.objects.all().delete()	
	return HttpResponse('Cleared')	
	
def displayForm(request,form_id):
	#Displays the required form and handles submission
	
	try:
		form_id=int(form_id)
	except ValueError:
		raise Http404
		
	kwargs={}	
	
	frm=Form.objects.get(id=form_id)
	questions=Question.objects.filter(form=frm).order_by('id').values()
	options=[]
	properties=[]	
	for question in questions:
		if question['ques_type']=='radio':
			ques=Question.objects.get(id=question['id'])
			for option in Option.objects.filter(question=ques).order_by('id').values():
				options.append([option['opt'],option['opt']])
		properties.append({'ques':question['question'],'ques_type':question['ques_type'],'required':question['required'],'opts':options,'id':question['id']})	
	
	form=CustomForm(request.POST or None, properties=properties)
	if form.is_valid():
		response=form.cleaned_data
		usr=MyUser.objects.create()
		for key in response:
			ques=Question.objects.get(id=int(key))
			Responses.objects.create(form=frm, question=ques, resp=response[key],myuser=usr)
			
			#Setting up the argument list for the dynamic model's create call
			kwargs['ques_'+key]=response[key]
			
		#Getting the dynamic model
		dynModel=dynamic_model(form_id)
		
		#Performing the create query using kwargs
		dynModel.objects.create(**kwargs)
		
			
		return HttpResponseRedirect('/success/'+str(form_id))
	return render_to_response('form.html',{'form':form},context_instance=RequestContext(request))
	
def onSuccess(request, form_id):
	#Successful form submission
	try:
		form_id=int(form_id)
	except ValueError:
		raise Http404
	
	return render_to_response('success.html',{'form_id':form_id})
	
def showResults(request,form_id):
	#Shows the results for a particular form
	try:
		form_id=int(form_id)
	except ValueError:
		raise Http404
		
	#Doing it the normal way first. Getting results from the One table.
	
	form=Form.objects.get(id=form_id)
	questions=Question.objects.filter(form=form).order_by('id')
	questions_list=questions.values_list('question',flat=True)
	all_responses=Responses.objects.filter(form=form).order_by('myuser','question').values_list('resp',flat=True)
	title=form.title
	#Grouping complete responses together (not the best way, though)
	responses=[]
	splitsize=len(all_responses) / len(questions_list)
	for i in range(splitsize):
		responses.append(all_responses[(i*len(questions_list)):(i*len(questions_list)+len(questions_list))])
		
	#Doing it through dynamic models. Getting results from the response table that was set up uniquely for this form.
	dynModel=dynamic_model(form_id)
	all_responses=dynModel.objects.all().order_by('id').values()
	
	#Setting up the response list to be passed to the template
	dyn_responses=[]
	for response in all_responses:
		one_response=[]
		for question in questions:
			one_response.append(response['ques_'+str(question.id)])
		dyn_responses.append(one_response)	
	
	return render_to_response('results.html',{'questions':questions_list,'responses':dyn_responses,'title':title})
	

def deleteForm(form_id):
	# Takes a backup of the form, and deletes it completely
	
	try:
		form_id=int(form_id)
	except ValueError:
		raise Http404
	
	form=Form.objects.get(id=form_id)
	
	#Storing to file
	dumpToFile(form)
	
	#Performing deletions
	Option.objects.filter(form=form).delete()
	Question.objects.filter(form=form).delete()
	
	#Dropping response table
	table_name='customforms_response_form_'+str(form.id)
	sqlite_query='DROP TABLE '+table_name
	cursor=connection.cursor()
	cursor.execute(sqlite_query)
	
	#Changing status of form to '0' to show that it's been deleted
	form.active=0;
	form.save();
	
def restoreForm(form_id):
	#Restores the specified form from the backup file
	
	try:
		form_id=int(form_id)
	except ValueError:
		raise Http404
		
	form=Form.objects.get(id=form_id)
	
	#Restoring from file
	restoreFromFile(form)
	
	#Changing status of form to '1' to show that it's been deleted
	form.active=1;
	form.save();	
	
	


	
	
		
	